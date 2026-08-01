from __future__ import annotations

import hashlib
from pathlib import Path
import re
import urllib.error
from urllib.parse import quote, urlsplit, urlunsplit

from utils.cli import build_common_parser
from utils.fs_utils import ensure_dir, load_jsonl, write_jsonl
from utils.html_utils import html_to_text
from utils.http_utils import HttpClient
from utils.logging_utils import configure_logger
from utils.metadata import infer_extension


def target_raw_path(root: Path, source_id: str, url: str, extension: str) -> Path:
    hashed = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    filename = f"{hashed}.{extension}"
    return root / "data" / "raw" / source_id / filename


def public_download_url(url: str) -> str:
    """Resolve an explicitly shared Google Drive file without authentication.

    This uses only the file identifier exposed by the official archive link;
    it intentionally does not handle confirmation tokens or restricted files.
    """
    parts = urlsplit(url)
    url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), quote(parts.query, safe="=&%"), parts.fragment))
    match = re.match(r"https://drive\.google\.com/file/d/([^/]+)/", url)
    if match:
        return f"https://drive.usercontent.google.com/download?id={match.group(1)}&export=download"
    return url


def response_matches_extension(extension: str, content_type: str, content: bytes) -> bool:
    """Reject HTML/interstitial responses for candidates expected to be files."""
    if extension == "pdf":
        return content.startswith(b"%PDF-") and "html" not in content_type.lower()
    return "html" not in content_type.lower() or extension in {"html", "htm"}


def get_header_value(headers: dict[str, str], name: str) -> str:
    return headers.get(name, "") or headers.get(name.lower(), "")


def guessed_content_type(extension: str) -> str:
    return {
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "htm": "text/html; charset=utf-8",
        "html": "text/html; charset=utf-8",
        "pdf": "application/pdf",
        "zip": "application/zip",
    }.get(extension, "")


def checkpoint_path(root: Path) -> Path:
    return root / "data" / "manifests" / "download_checkpoint.jsonl"


def local_file_is_valid(path: Path, extension: str) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    if extension == "pdf":
        with path.open("rb") as handle:
            return handle.read(5) == b"%PDF-"
    return True


def checkpoint_key(row: dict) -> str:
    return str(row.get("candidate_id") or f"{row.get('source_id', '')}::{row.get('source_url', '')}")


def terminal_failure_status(error: Exception) -> str | None:
    """Return a durable outcome only when the failure is specific and stable."""
    if isinstance(error, urllib.error.HTTPError) and error.code in {404, 410}:
        return f"http_{error.code}"
    if isinstance(error, PermissionError):
        return "policy_blocked"
    return None


def crawl_documents(root: Path, families: set[str] | None, dry_run: bool, limit: int | None) -> int:
    logger = configure_logger("crawl_source", root / "data" / "logs" / "download.log")
    errors_logger = configure_logger("crawl_source.errors", root / "data" / "logs" / "errors.log")
    client = HttpClient(logger=logger, dry_run=dry_run)
    discovered = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
    if families:
        discovered = [row for row in discovered if row["olympiad_family"] in families]
    if limit is not None:
        discovered = discovered[:limit]

    completed = {checkpoint_key(row): row for row in load_jsonl(checkpoint_path(root))}
    downloads: list[dict] = []
    for row in discovered:
        url = row["source_url"]
        notes = str(row.get("notes", ""))
        if row.get("access_mode", "download") == "discovery_only" or "discovery_only" in notes:
            logger.info("DOWNLOAD skip_discovery_only url=%s notes=%s", url, row.get("notes", ""))
            continue
        if row.get("source_id") == "owao_tasks_official" and "external_share=" in notes:
            logger.info("DOWNLOAD skip_external_share url=%s notes=%s", url, notes)
            continue
        extension = str(row.get("extension") or infer_extension(url))
        raw_path = target_raw_path(root, row["source_id"], url, extension)
        legacy_bin_path = target_raw_path(root, row["source_id"], url, "bin") if extension != "bin" else raw_path
        txt_path = raw_path.with_suffix(".txt")
        existing_raw_path = raw_path if raw_path.exists() else legacy_bin_path if legacy_bin_path.exists() else None
        existing_txt_path = existing_raw_path.with_suffix(".txt") if existing_raw_path is not None else txt_path

        checkpoint = completed.get(checkpoint_key(row))
        if checkpoint and (str(checkpoint.get("status", "")).startswith("http_") or checkpoint.get("status") in {"policy_blocked", "rejected_content"}):
            logger.info("DOWNLOAD skip_terminal_outcome url=%s status=%s", url, checkpoint["status"])
            continue
        if checkpoint and local_file_is_valid(Path(str(checkpoint.get("raw_path", ""))), extension):
            # Discovery metadata is authoritative on every global refresh.
            # Preserve only the validated local-download facts from a prior
            # checkpoint; otherwise a corrected family/source classification
            # would remain stale forever under resume.
            operational_fields = {
                key: checkpoint[key]
                for key in (
                    "raw_path", "txt_path", "status", "content_type", "request_url",
                    "final_url", "http_status", "bytes", "content_validation", "downloaded_at",
                )
                if key in checkpoint
            }
            downloads.append({**row, **operational_fields})
            continue

        if existing_raw_path is not None and local_file_is_valid(existing_raw_path, extension):
            logger.info("DOWNLOAD skip_existing url=%s path=%s", url, existing_raw_path)
            txt_saved = str(existing_txt_path) if existing_txt_path.exists() else ""
            content_type = guessed_content_type(extension)
            if txt_saved:
                content_type = "text/html; charset=utf-8"
            download_record = dict(row)
            download_record.update(
                {
                    "raw_path": str(existing_raw_path),
                    "txt_path": txt_saved,
                    "status": "existing",
                    "content_type": content_type,
                }
            )
            downloads.append(download_record)
            completed[checkpoint_key(row)] = download_record
            write_jsonl(checkpoint_path(root), completed.values())
            continue

        request_url = public_download_url(url)
        try:
            response = client.fetch(request_url)
        except Exception as error:
            errors_logger.error("DOWNLOAD failed url=%s error_type=%s error=%s", url, type(error).__name__, error)
            terminal_status = terminal_failure_status(error)
            if terminal_status:
                completed[checkpoint_key(row)] = {
                    **row,
                    "status": terminal_status,
                    "failure_type": type(error).__name__,
                    "failure_detail": str(error),
                    "request_url": request_url,
                }
                write_jsonl(checkpoint_path(root), completed.values())
            continue

        content_type = get_header_value(response.headers, "Content-Type")
        if extension in {"pdf", "doc", "docx", "zip"} and not response_matches_extension(extension, content_type, response.content):
            errors_logger.error("DOWNLOAD rejected_content url=%s final_url=%s expected=%s content_type=%s", url, response.final_url, extension, content_type)
            completed[checkpoint_key(row)] = {
                **row,
                "status": "rejected_content",
                "request_url": request_url,
                "final_url": response.final_url,
                "http_status": response.status_code,
                "content_type": content_type,
            }
            write_jsonl(checkpoint_path(root), completed.values())
            continue
        if infer_extension(url) in {"pdf", "doc", "docx", "zip"} and "html" in content_type.lower():
            page_text = html_to_text(response.text).lower()
            if any(token in page_text for token in ("login", "sign in", "войти", "авторизац")):
                errors_logger.error("DOWNLOAD skipped_login_page url=%s final_url=%s", url, response.final_url)
                continue

        if dry_run:
            download_record = dict(row)
            download_record.update({"raw_path": str(raw_path), "txt_path": "", "status": "dry_run"})
            downloads.append(download_record)
            continue

        ensure_dir(raw_path.parent)
        raw_path.write_bytes(response.content)
        logger.info("DOWNLOAD saved url=%s path=%s bytes=%s", url, raw_path, len(response.content))

        txt_saved = ""
        if infer_extension(url, content_type) in {"html", "htm"}:
            txt_payload = html_to_text(response.text)
            txt_path.write_text(txt_payload, encoding="utf-8")
            txt_saved = str(txt_path)

        download_record = dict(row)
        download_record.update(
            {
                "raw_path": str(raw_path),
                "txt_path": txt_saved,
                "status": "downloaded",
                "content_type": content_type,
                "request_url": request_url,
                "final_url": response.final_url,
                "http_status": response.status_code,
                "bytes": len(response.content),
                "content_validation": "pdf_signature" if extension == "pdf" else "accepted_non_html",
            }
        )
        downloads.append(download_record)
        completed[checkpoint_key(row)] = download_record
        write_jsonl(checkpoint_path(root), completed.values())

    # Replace records for candidates considered in this crawl rather than
    # appending them: a completed global resume must be idempotent.
    refreshed_keys = {checkpoint_key(row) for row in discovered}
    existing = [
        row for row in load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
        if checkpoint_key(row) not in refreshed_keys
    ]
    merged = {checkpoint_key(row): row for row in [*existing, *downloads]}
    write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", merged.values())
    logger.info("DOWNLOAD complete count=%s", len(downloads))
    return 0


def main() -> int:
    parser = build_common_parser("Download discovered documents into data/raw.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return crawl_documents(args.root, families, args.dry_run, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())

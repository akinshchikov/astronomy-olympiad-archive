from __future__ import annotations

import hashlib
from pathlib import Path

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


def crawl_documents(root: Path, families: set[str] | None, dry_run: bool, limit: int | None) -> int:
    logger = configure_logger("crawl_source", root / "data" / "logs" / "download.log")
    errors_logger = configure_logger("crawl_source.errors", root / "data" / "logs" / "errors.log")
    client = HttpClient(logger=logger, dry_run=dry_run)
    discovered = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
    if families:
        discovered = [row for row in discovered if row["olympiad_family"] in families]
    if limit is not None:
        discovered = discovered[:limit]

    downloads: list[dict] = []
    for row in discovered:
        url = row["source_url"]
        notes = str(row.get("notes", ""))
        if "discovery_only" in notes:
            logger.info("DOWNLOAD skip_discovery_only url=%s notes=%s", url, row.get("notes", ""))
            continue
        if row.get("source_id") == "owao_tasks_official" and "external_share=" in notes:
            logger.info("DOWNLOAD skip_external_share url=%s notes=%s", url, notes)
            continue
        extension = infer_extension(url)
        raw_path = target_raw_path(root, row["source_id"], url, extension)
        legacy_bin_path = target_raw_path(root, row["source_id"], url, "bin") if extension != "bin" else raw_path
        txt_path = raw_path.with_suffix(".txt")
        existing_raw_path = raw_path if raw_path.exists() else legacy_bin_path if legacy_bin_path.exists() else None
        existing_txt_path = existing_raw_path.with_suffix(".txt") if existing_raw_path is not None else txt_path

        if existing_raw_path is not None:
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
            continue

        try:
            response = client.fetch(url)
        except Exception as error:
            errors_logger.error("DOWNLOAD failed url=%s error_type=%s error=%s", url, type(error).__name__, error)
            continue

        content_type = get_header_value(response.headers, "Content-Type")
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
            }
        )
        downloads.append(download_record)

    write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", downloads)
    logger.info("DOWNLOAD complete count=%s", len(downloads))
    return 0


def main() -> int:
    parser = build_common_parser("Download discovered documents into data/raw.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return crawl_documents(args.root, families, args.dry_run, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())

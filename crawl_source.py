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
        extension = infer_extension(url)
        raw_path = target_raw_path(root, row["source_id"], url, extension)
        txt_path = raw_path.with_suffix(".txt")

        if raw_path.exists():
            logger.info("DOWNLOAD skip_existing url=%s path=%s", url, raw_path)
            download_record = dict(row)
            download_record.update(
                {
                    "raw_path": str(raw_path),
                    "txt_path": str(txt_path) if txt_path.exists() else "",
                    "status": "existing",
                }
            )
            downloads.append(download_record)
            continue

        try:
            response = client.fetch(url)
        except Exception as error:
            errors_logger.error("DOWNLOAD failed url=%s error=%s", url, error)
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
        if infer_extension(url, response.headers.get("Content-Type", "")) in {"html", "htm"}:
            txt_payload = html_to_text(response.text)
            txt_path.write_text(txt_payload, encoding="utf-8")
            txt_saved = str(txt_path)

        download_record = dict(row)
        download_record.update(
            {
                "raw_path": str(raw_path),
                "txt_path": txt_saved,
                "status": "downloaded",
                "content_type": response.headers.get("Content-Type", ""),
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


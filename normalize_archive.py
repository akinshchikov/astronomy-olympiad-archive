from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import ensure_dir, load_jsonl, write_json, write_jsonl
from utils.logging_utils import configure_logger
from utils.metadata import (
    infer_detail_tag,
    infer_document_type,
    infer_extension,
    infer_stage,
    infer_year,
    normalize_filename,
    path_slug,
    year_tag,
)

OBJECTS_DIRNAME = "objects"
EVENT_METADATA_FILENAME = "event-metadata.json"
EVENT_SOURCE_URLS_FILENAME = "event-source-urls.txt"
EVENT_RELATIONS_FILENAME = "event-relations.json"
OWAO_SOURCE_ID = "owao_tasks_official"


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def link_or_copy(source: Path, target: Path) -> None:
    ensure_dir(target.parent)
    if target.exists():
        return
    try:
        os.link(source, target)
    except OSError:
        target.write_bytes(source.read_bytes())


def resolve_year(row: dict, max_reasonable_year: int) -> int | None:
    candidates = (
        infer_year(str(row.get("filename_original", ""))),
        infer_year(str(row.get("source_url", ""))),
        infer_year(str(row.get("parent_page_url", ""))),
        row.get("year"),
    )
    for candidate in candidates:
        if isinstance(candidate, int) and candidate <= max_reasonable_year:
            return candidate
    return None


def is_relevant_entry(row: dict) -> bool:
    if row["document_type"] != "info":
        return True
    if row["year"] is not None:
        return True
    if row["stage_or_round"] != "unknown":
        return True

    text = " ".join(
        [
            str(row.get("source_title", "")),
            str(row.get("parent_page_title", "")),
            str(row.get("source_url", "")),
            str(row.get("notes", "")),
        ]
    ).lower()
    relevance_tokens = (
        "problem",
        "solution",
        "marking",
        "theory",
        "observation",
        "regional",
        "final",
        "teor",
        "prak",
        "задани",
        "решен",
        "ответ",
        "критер",
        "200",
        "201",
        "202",
    )
    return any(token in text for token in relevance_tokens)


def normalize(root: Path, families: set[str] | None, dry_run: bool, limit: int | None) -> int:
    logger = configure_logger("normalize_archive", root / "data" / "logs" / "normalization.log")
    download_manifest = load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
    if families:
        download_manifest = [row for row in download_manifest if row["olympiad_family"] in families]
    if limit is not None:
        download_manifest = download_manifest[:limit]

    normalized_entries: list[dict] = []
    event_groups: dict[tuple[str, int | None, str], list[dict]] = defaultdict(list)
    object_store = ensure_dir(root / "data" / "archive" / OBJECTS_DIRNAME)
    used_archive_paths: dict[str, str] = {}
    max_reasonable_year = datetime.now(timezone.utc).year + 1

    for row in download_manifest:
        if not is_relevant_entry(row):
            logger.info("NORMALIZE skip_irrelevant url=%s", row["source_url"])
            continue
        raw_path = Path(row["raw_path"])
        if dry_run and not raw_path.exists():
            logger.info("NORMALIZE dry_run skip_missing %s", raw_path)
            continue
        if not raw_path.exists():
            logger.warning("NORMALIZE missing_raw %s", raw_path)
            continue

        sha256 = sha256_of_file(raw_path)
        extension = raw_path.suffix.lstrip(".").lower() or row["extension"]
        if extension == "bin":
            extension = infer_extension(row["source_url"], row.get("content_type", ""))
        year = resolve_year(row, max_reasonable_year)
        document_type = row["document_type"]
        is_owao_seed_page = row.get("source_id") == OWAO_SOURCE_ID and "seed_page=true" in str(row.get("notes", ""))
        inferred_document_type, _ = infer_document_type(
            str(row.get("filename_original", "")),
            str(row.get("source_title", "")),
            str(row.get("source_url", "")),
            str(row.get("parent_page_title", "")),
            str(row.get("parent_page_url", "")),
        )
        if not is_owao_seed_page and document_type == "info" and inferred_document_type != "info":
            document_type = inferred_document_type
        elif document_type == "tasks" and inferred_document_type in {"solutions", "marking", "analysis"}:
            document_type = inferred_document_type
        stage_or_round = row["stage_or_round"]
        round_detail = row.get("round_detail")
        if stage_or_round == "unknown" or not round_detail:
            inferred_stage, inferred_round_detail = infer_stage(
                row["olympiad_family"],
                str(row.get("filename_original", "")),
                str(row.get("source_title", "")),
                str(row["source_url"]),
                str(row.get("parent_page_title", "")),
                str(row.get("parent_page_url", "")),
            )
            if stage_or_round == "unknown" and inferred_stage != "unknown":
                stage_or_round = inferred_stage
            if not round_detail and inferred_round_detail:
                round_detail = inferred_round_detail
        object_path = object_store / f"{sha256}.{extension}"
        if not dry_run and not object_path.exists():
            object_path.write_bytes(raw_path.read_bytes())

        detail_tag = infer_detail_tag(
            olympiad_family=row["olympiad_family"],
            stage_or_round=stage_or_round,
            document_type=document_type,
            language=row["language"],
            round_detail=round_detail,
            extension=extension,
            filename_original=str(row.get("filename_original", "")),
            source_title=str(row.get("source_title", "")),
            source_url=str(row["source_url"]),
            parent_page_title=str(row.get("parent_page_title", "")),
            parent_page_url=str(row.get("parent_page_url", "")),
            source_role=str(row.get("source_role", "")),
        )

        normalized_filename = normalize_filename(
            year=year,
            olympiad_family=row["olympiad_family"],
            stage_or_round=stage_or_round,
            document_type=document_type,
            language=row["language"],
            detail_tag=detail_tag,
            variant_tag=row["variant_tag"],
            extension=extension,
        )

        archive_dir = (
            root
            / "data"
            / "archive"
            / path_slug(row["olympiad_family"], fallback="olympiad")
            / year_tag(year)
            / path_slug(stage_or_round, fallback="stage")
            / path_slug(document_type, fallback="document")
        )
        archive_path = archive_dir / normalized_filename
        if str(archive_path) in used_archive_paths and used_archive_paths[str(archive_path)] != sha256:
            stem = archive_path.stem
            suffix = archive_path.suffix
            counter = 2
            while True:
                candidate = archive_dir / f"{stem}-v{counter}{suffix}"
                if str(candidate) not in used_archive_paths or used_archive_paths[str(candidate)] == sha256:
                    archive_path = candidate
                    normalized_filename = archive_path.name
                    break
                counter += 1
        used_archive_paths[str(archive_path)] = sha256

        if not dry_run:
            link_or_copy(object_path, archive_path)

        entry = dict(row)
        entry.update(
            {
                "year": year,
                "stage_or_round": stage_or_round,
                "round_detail": round_detail,
                "document_type": document_type,
                "filename_normalized": normalized_filename,
                "archive_path": str(archive_path),
                "object_path": str(object_path),
                "sha256": sha256,
                "file_size": raw_path.stat().st_size,
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
                "detail_tag": detail_tag,
                "canonical_candidate": False,
                "relation_group_id": "",
                "relation_type": "",
                "relation_confidence": 0.0,
                "same_event_confidence": 0.0,
                "same_content_confidence": 0.0,
            }
        )
        normalized_entries.append(entry)
        event_groups[(row["olympiad_family"], year, stage_or_round)].append(entry)
        logger.info("NORMALIZE entry path=%s sha256=%s", archive_path, sha256)

    write_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl", normalized_entries)

    for (family, year, stage), entries in event_groups.items():
        info_dir = (
            root
            / "data"
            / "archive"
            / path_slug(family, fallback="olympiad")
            / year_tag(year)
            / path_slug(stage, fallback="stage")
            / "info"
        )
        ensure_dir(info_dir)
        write_json(info_dir / EVENT_METADATA_FILENAME, entries)
        with (info_dir / EVENT_SOURCE_URLS_FILENAME).open("w", encoding="utf-8") as handle:
            for url in sorted({entry["source_url"] for entry in entries}):
                handle.write(url)
                handle.write("\n")
        write_json(info_dir / EVENT_RELATIONS_FILENAME, [])

    return 0


def main() -> int:
    parser = build_common_parser("Normalize raw downloads into archive structure.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return normalize(args.root, families, args.dry_run, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())

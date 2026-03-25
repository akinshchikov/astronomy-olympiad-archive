from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import ensure_dir, load_jsonl, write_json, write_jsonl
from utils.html_utils import extract_links, html_to_text
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
CONTAINER_SOURCE_IDS = {
    "ioaa_past_olympiads",
    "ioaa_problems",
    "ioaa_proceedings",
    "owao_tasks_official",
    "russia_team_qual_archive",
    "spbao_official",
    "spbao_year_class_pages",
    "vsosh_astroedu_archive",
}
DIRECT_FILE_EXTENSIONS = {"pdf", "doc", "docx", "zip"}


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


def seed_context(row: dict) -> dict:
    return dict(row.get("seed_context") or {})


def context_year(row: dict) -> int | None:
    context = seed_context(row)
    for key in ("year", "archive_year", "season_end"):
        candidate = context.get(key)
        if isinstance(candidate, int):
            return candidate
    return None


def load_text_hint(row: dict, raw_path: Path) -> str:
    txt_path_value = str(row.get("txt_path", "") or "")
    if txt_path_value:
        txt_path = Path(txt_path_value)
        if txt_path.exists():
            return txt_path.read_text(encoding="utf-8", errors="ignore")

    inferred_extension = infer_extension(str(row.get("source_url", "")), str(row.get("content_type", "")))
    if raw_path.suffix.lower() in {".html", ".htm"} or inferred_extension in {"html", "htm"}:
        try:
            raw_html = raw_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""
        return html_to_text(raw_html)

    return ""


def resolve_extension(row: dict, raw_path: Path) -> str:
    extension = raw_path.suffix.lstrip(".").lower() or str(row.get("extension", "")).lower()
    if extension == "bin":
        txt_path_value = str(row.get("txt_path", "") or "")
        if txt_path_value and Path(txt_path_value).exists():
            return "html"
        notes = str(row.get("notes", "")).lower()
        if "source_kind=html" in notes:
            return "html"
        inferred = infer_extension(str(row.get("source_url", "")), str(row.get("content_type", "")))
        if inferred != "bin":
            return "html" if inferred == "htm" else inferred
        row_extension = str(row.get("extension", "")).lower()
        if row_extension and row_extension != "bin":
            return "html" if row_extension == "htm" else row_extension
    return "html" if extension == "htm" else extension


def resolve_year(row: dict, max_reasonable_year: int, text_hint: str) -> int | None:
    candidates = (
        context_year(row),
        infer_year(str(row.get("filename_original", ""))),
        infer_year(str(row.get("source_title", ""))),
        infer_year(str(row.get("source_url", ""))),
        infer_year(str(row.get("parent_page_title", ""))),
        infer_year(str(row.get("parent_page_url", ""))),
        infer_year(text_hint),
        row.get("year"),
    )
    for candidate in candidates:
        if isinstance(candidate, int) and candidate <= max_reasonable_year:
            return candidate
    return None


def page_has_problem_statements(page_text: str) -> bool:
    lowered = page_text.lower()
    first_problem = re.search(r"(?:^|\s)(?:1[.)]|problem\s*1|задач[аи]?\s*1)\s+\S", lowered)
    second_problem = re.search(r"(?:^|\s)(?:2[.)]|problem\s*2|задач[аи]?\s*2)\s+\S", lowered)
    return bool(first_problem and second_problem)


def is_non_artifact_html_entry(row: dict, raw_path: Path, extension: str, text_hint: str) -> bool:
    if extension not in {"html", "htm"}:
        return False

    notes = str(row.get("notes", "")).lower()
    source_id = str(row.get("source_id", ""))
    lowered_text = text_hint.lower()

    if source_id == "spbao_year_class_pages":
        return True
    if "html_container=true" in notes:
        return True
    if "к сожалению, у нас нет заданий" in lowered_text:
        return True
    if "seed_page=true" in notes and source_id in CONTAINER_SOURCE_IDS:
        return True

    try:
        raw_html = raw_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        raw_html = ""
    direct_file_links = [
        link
        for link in extract_links(raw_html, str(row.get("source_url", "")))
        if infer_extension(link["href"]) in DIRECT_FILE_EXTENSIONS
    ]
    if direct_file_links and not page_has_problem_statements(text_hint):
        return True

    return False


def compute_direct_file_preference_keys(
    download_manifest: list[dict],
    max_reasonable_year: int,
) -> set[tuple[str, str, str, int | None, str, str, str | None, str]]:
    keys: set[tuple[str, str, str, int | None, str, str, str | None, str]] = set()
    for row in download_manifest:
        raw_path_value = str(row.get("raw_path", "") or "")
        if not raw_path_value:
            continue
        raw_path = Path(raw_path_value)
        extension = resolve_extension(row, raw_path)
        if extension in {"html", "htm"}:
            continue

        resolved_year = resolve_year(row, max_reasonable_year, "")
        context = seed_context(row)
        stage_or_round = str(context.get("stage_or_round") or row.get("stage_or_round", "unknown"))
        round_detail = str(context.get("round_detail") or row.get("round_detail") or "") or None
        language = str(row.get("language", "unknown"))
        document_type = str(row.get("document_type", "info"))
        inferred_document_type, _ = infer_document_type(
            str(row.get("filename_original", "")),
            str(row.get("source_title", "")),
            str(row.get("source_url", "")),
            str(row.get("parent_page_title", "")),
            str(row.get("parent_page_url", "")),
        )
        if document_type == "info" and inferred_document_type != "info":
            document_type = inferred_document_type
        if stage_or_round == "unknown":
            inferred_stage, _ = infer_stage(
                str(row.get("olympiad_family", "")),
                str(row.get("filename_original", "")),
                str(row.get("source_title", "")),
                str(row.get("source_url", "")),
                str(row.get("parent_page_title", "")),
                str(row.get("parent_page_url", "")),
            )
            if inferred_stage != "unknown":
                stage_or_round = inferred_stage

        keys.add(
            (
                str(row.get("source_id", "")),
                str(row.get("source_url", "")),
                str(row.get("olympiad_family", "")),
                resolved_year,
                stage_or_round,
                document_type,
                round_detail,
                language,
            )
        )
        parent_page_url = str(row.get("parent_page_url", "") or "")
        if parent_page_url:
            keys.add(
                (
                    str(row.get("source_id", "")),
                    parent_page_url,
                    str(row.get("olympiad_family", "")),
                    resolved_year,
                    stage_or_round,
                    document_type,
                    round_detail,
                    language,
                )
            )
    return keys


def should_skip_due_to_preferred_direct_file(
    row: dict,
    *,
    extension: str,
    year: int | None,
    stage_or_round: str,
    document_type: str,
    round_detail: str | None,
    direct_file_keys: set[tuple[str, str, str, int | None, str, str, str | None, str]],
) -> bool:
    if extension not in {"html", "htm"}:
        return False

    key = (
        str(row.get("source_id", "")),
        str(row.get("source_url", "")),
        str(row.get("olympiad_family", "")),
        year,
        stage_or_round,
        document_type,
        round_detail,
        str(row.get("language", "unknown")),
    )
    return key in direct_file_keys


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
    direct_file_keys = compute_direct_file_preference_keys(download_manifest, max_reasonable_year)

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

        text_hint = load_text_hint(row, raw_path)
        sha256 = sha256_of_file(raw_path)
        extension = resolve_extension(row, raw_path)
        if is_non_artifact_html_entry(row, raw_path, extension, text_hint):
            logger.info("NORMALIZE skip_non_artifact_html url=%s", row["source_url"])
            continue

        year = resolve_year(row, max_reasonable_year, text_hint)
        context = seed_context(row)
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
        stage_or_round = str(context.get("stage_or_round") or row["stage_or_round"])
        round_detail = str(context.get("round_detail") or row.get("round_detail") or "") or None
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
        if should_skip_due_to_preferred_direct_file(
            row,
            extension=extension,
            year=year,
            stage_or_round=stage_or_round,
            document_type=document_type,
            round_detail=round_detail,
            direct_file_keys=direct_file_keys,
        ):
            logger.info("NORMALIZE skip_html_shadowed_by_direct_file url=%s", row["source_url"])
            continue
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
                "extension": extension,
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

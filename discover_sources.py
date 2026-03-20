from __future__ import annotations

import csv
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import ensure_dir, write_jsonl
from utils.html_utils import extract_links, extract_title
from utils.http_utils import HttpClient
from utils.logging_utils import configure_logger
from utils.metadata import (
    confidence_score,
    decoded_filename,
    decoded_url_path,
    infer_document_type,
    infer_extension,
    infer_language,
    infer_stage,
    infer_variant_tag,
    infer_year,
    source_domain,
)
from utils.source_configs import SOURCE_DEFINITIONS, iter_seed_requests


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "zip", "html", "htm"}
STRUVE_SOURCE_ID = "struve_moscow_year_pages"
OWAO_SOURCE_ID = "owao_tasks_official"


def build_source_candidates_csv(root: Path, families: set[str] | None) -> list[dict]:
    rows: list[dict] = []
    for source in SOURCE_DEFINITIONS:
        if families and source.olympiad_family not in families:
            continue
        seeds = iter_seed_requests(source)
        rows.append(
            {
                "source_id": source.source_id,
                "label": source.label,
                "olympiad_family": source.olympiad_family,
                "source_role": source.source_role,
                "source_priority": source.source_priority,
                "seed_count": len(seeds),
                "notes": source.notes,
            }
        )

    out_path = root / "data" / "manifests" / "source_candidates.csv"
    ensure_dir(out_path.parent)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    return rows


def should_record_link(url: str) -> bool:
    decoded_path = decoded_url_path(url).lower()
    if any(decoded_path.endswith(f".{extension}") for extension in ALLOWED_EXTENSIONS):
        return True
    return False


def is_struve_seed(seed: dict) -> bool:
    return seed.get("source_id") == STRUVE_SOURCE_ID


def is_owao_seed(seed: dict) -> bool:
    return seed.get("source_id") == OWAO_SOURCE_ID


def should_record_seed_page(seed: dict) -> bool:
    return not is_struve_seed(seed)


def should_record_seed_link(seed: dict, link_text: str, href: str) -> bool:
    if not should_record_link(href):
        return False
    if is_struve_seed(seed):
        # The shared vos.olimpiada.ru year pages also contain broader VsOSH material,
        # so the Struve source keeps only Struve links and does not record the generic seed page.
        return "struve" in f"{link_text} {href}".lower()
    return True


def infer_family(default_family: str, *texts: str) -> str:
    text = " ".join(texts).lower()
    if "ioaa" in text or "gecaa" in text:
        return "ioaa"
    if default_family == "iao":
        return "iao"
    return default_family


def record_seed_page(seed: dict, title: str, extension: str = "html") -> dict:
    family = infer_family(seed["olympiad_family"], seed["url"], title)
    year = infer_year(f"{seed['url']} {title}")
    document_type, extra_types = infer_document_type(title, seed["url"], seed["source_id"])
    if is_owao_seed(seed):
        document_type, extra_types = "info", []
    stage_or_round, round_detail = infer_stage(family, title, seed["url"])
    language = infer_language(title)
    variant_tag = infer_variant_tag(seed["source_role"], title or seed["source_id"], seed["url"], extra_types)
    return {
        "candidate_id": hashlib.sha1(seed["url"].encode("utf-8")).hexdigest(),
        "source_id": seed["source_id"],
        "olympiad_family": family,
        "year": year,
        "stage_or_round": stage_or_round,
        "language": language,
        "document_type": document_type,
        "source_url": seed["url"],
        "source_domain": source_domain(seed["url"]),
        "source_title": title,
        "source_priority": seed["source_priority"],
        "source_role": seed["source_role"],
        "parent_page_url": seed["url"],
        "parent_page_title": title,
        "filename_original": decoded_filename(seed["url"]) or "page.html",
        "extension": extension,
        "variant_tag": variant_tag,
        "round_detail": round_detail,
        "notes": f"seed_page=true; source_kind=html; extra_types={','.join(extra_types)}",
        "confidence": confidence_score(year, stage_or_round, document_type, title),
    }


def discover_documents(root: Path, families: set[str] | None, dry_run: bool, limit: int | None) -> int:
    logger = configure_logger("discover_sources", root / "data" / "logs" / "crawl.log")
    errors_logger = configure_logger("discover_sources.errors", root / "data" / "logs" / "errors.log")
    client = HttpClient(logger=logger, dry_run=dry_run)
    source_rows = build_source_candidates_csv(root, families)
    logger.info("SOURCE_CANDIDATES count=%s", len(source_rows))

    seeds = []
    for source in SOURCE_DEFINITIONS:
        if families and source.olympiad_family not in families:
            continue
        seeds.extend(seed.to_dict() for seed in iter_seed_requests(source))

    if limit is not None:
        seeds = seeds[:limit]

    discovered: dict[tuple[str, str], dict] = {}
    coverage: dict[tuple[str, int | None, str], set[str]] = defaultdict(set)

    for seed in seeds:
        logger.info("SEED start source_id=%s url=%s", seed["source_id"], seed["url"])
        try:
            response = client.fetch(seed["url"])
        except Exception as error:
            errors_logger.error("SEED failed source_id=%s url=%s error=%s", seed["source_id"], seed["url"], error)
            continue

        if response.status_code and response.status_code >= 400:
            errors_logger.error("SEED bad_status source_id=%s url=%s status=%s", seed["source_id"], seed["url"], response.status_code)
            continue

        title = extract_title(response.text)
        if should_record_seed_page(seed):
            seed_page_entry = record_seed_page(seed, title)
            discovered[(seed["source_id"], seed["url"])] = seed_page_entry

        links = extract_links(response.text, response.final_url)
        for link in links:
            href = link["href"]
            if not should_record_seed_link(seed, link["text"], href):
                continue
            title_bits = [link["text"], title, href]
            family = infer_family(seed["olympiad_family"], href, link["text"], title)
            year = infer_year(" ".join(filter(None, title_bits)))
            document_type, extra_types = infer_document_type(*title_bits)
            stage_or_round, round_detail = infer_stage(family, *title_bits)
            language = infer_language(link["text"], href)
            variant_tag = infer_variant_tag(seed["source_role"], link["text"] or title, href, extra_types)
            candidate_id = hashlib.sha1(f"{seed['source_id']}::{href}".encode("utf-8")).hexdigest()
            key = (seed["source_id"], href)
            if key not in discovered:
                discovered[key] = {
                    "candidate_id": candidate_id,
                    "source_id": seed["source_id"],
                    "olympiad_family": family,
                    "year": year,
                    "stage_or_round": stage_or_round,
                    "language": language,
                    "document_type": document_type,
                    "source_url": href,
                    "source_domain": source_domain(href),
                    "source_title": link["text"] or title,
                    "source_priority": seed["source_priority"],
                    "source_role": seed["source_role"],
                    "parent_page_url": seed["url"],
                    "parent_page_title": title,
                    "filename_original": decoded_filename(href) or "download",
                    "extension": infer_extension(href),
                    "variant_tag": variant_tag,
                    "round_detail": round_detail,
                    "notes": f"extra_types={','.join(extra_types)}",
                    "confidence": confidence_score(year, stage_or_round, document_type, link["text"] or title),
                }
            else:
                notes = discovered[key]["notes"]
                parent = seed["url"]
                if parent not in notes:
                    discovered[key]["notes"] = notes + f"; seen_from={parent}"

            coverage[(family, year, stage_or_round)].add(document_type)

    discovered_rows = sorted(
        discovered.values(),
        key=lambda row: (
            row["olympiad_family"],
            row["year"] or 0,
            row["stage_or_round"],
            row["document_type"],
            row["source_url"],
        ),
    )
    write_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl", discovered_rows)

    coverage_rows = []
    for (family, year, stage), doc_types in sorted(
        coverage.items(),
        key=lambda item: (item[0][0], item[0][1] or 0, item[0][2]),
    ):
        coverage_rows.append(
            {
                "olympiad_family": family,
                "year": year,
                "stage_or_round": stage,
                "document_types_found": ",".join(sorted(doc_types)),
                "num_document_types": len(doc_types),
            }
        )

    coverage_path = root / "data" / "manifests" / "discovery_coverage.csv"
    ensure_dir(coverage_path.parent)
    with coverage_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage_rows[0].keys()) if coverage_rows else [])
        if coverage_rows:
            writer.writeheader()
            writer.writerows(coverage_rows)

    logger.info("DISCOVERY done count=%s", len(discovered_rows))
    return 0


def main() -> int:
    parser = build_common_parser("Discover public astronomy olympiad sources and candidate documents.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return discover_documents(args.root, families, args.dry_run, args.limit)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import load_jsonl
from utils.logging_utils import configure_logger
from utils.metadata import PRIORITY_FAMILIES


def build(root: Path, families: set[str] | None) -> int:
    logger = configure_logger("build_indices", root / "data" / "logs" / "normalization.log")
    entries = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
    discovered_rows = load_jsonl(root / "data" / "manifests" / "discovered_documents.jsonl")
    downloaded_rows = load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
    if families:
        entries = [row for row in entries if row["olympiad_family"] in families]
        discovered_rows = [row for row in discovered_rows if row["olympiad_family"] in families]
        downloaded_rows = [row for row in downloaded_rows if row["olympiad_family"] in families]

    relation_groups_lookup = {}
    relation_groups_path = root / "data" / "indices" / "relation_groups.csv"
    if relation_groups_path.exists():
        with relation_groups_path.open("r", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                relation_groups_lookup[row["relation_group_id"]] = row

    objects: dict[str, dict] = {}
    olympiad_index: dict[tuple[str, int | None, str], dict] = {}
    relation_groups_per_event: dict[tuple[str, int | None, str], set[str]] = defaultdict(set)
    downloaded_candidate_ids = {row["candidate_id"] for row in downloaded_rows}
    missing_rows_by_family: dict[str, list[dict]] = defaultdict(list)
    for row in discovered_rows:
        if row["candidate_id"] not in downloaded_candidate_ids:
            missing_rows_by_family[row["olympiad_family"]].append(row)

    for entry in entries:
        objects.setdefault(
            entry["sha256"],
            {
                "sha256": entry["sha256"],
                "object_path": entry["object_path"],
                "extension": entry["extension"],
                "file_size": entry["file_size"],
                "representative_filename": entry["filename_normalized"],
                "source_count": 0,
                "source_urls": set(),
                "olympiad_family": entry["olympiad_family"],
                "year": entry["year"],
                "stage_or_round": entry["stage_or_round"],
                "document_type": entry["document_type"],
                "language": entry["language"],
            },
        )
        objects[entry["sha256"]]["source_count"] += 1
        objects[entry["sha256"]]["source_urls"].add(entry["source_url"])

        key = (entry["olympiad_family"], entry["year"], entry["stage_or_round"])
        if key not in olympiad_index:
            olympiad_index[key] = {
                "olympiad_family": entry["olympiad_family"],
                "year": entry["year"],
                "stage_or_round": entry["stage_or_round"],
                "has_tasks": False,
                "has_solutions": False,
                "has_marking": False,
                "has_analysis": False,
                "num_files": 0,
                "num_relation_groups": 0,
                "source_count": 0,
                "confidence": 0.0,
            }

        olympiad_index[key]["num_files"] += 1
        olympiad_index[key]["source_count"] += 1
        olympiad_index[key]["confidence"] = round(
            max(olympiad_index[key]["confidence"], float(entry.get("confidence", 0.0))),
            2,
        )
        if entry["document_type"] == "tasks":
            olympiad_index[key]["has_tasks"] = True
        elif entry["document_type"] == "solutions":
            olympiad_index[key]["has_solutions"] = True
        elif entry["document_type"] == "marking":
            olympiad_index[key]["has_marking"] = True
        elif entry["document_type"] == "analysis":
            olympiad_index[key]["has_analysis"] = True

        if entry.get("relation_group_id"):
            relation_groups_per_event[key].add(entry["relation_group_id"])

    for key, group_ids in relation_groups_per_event.items():
        olympiad_index[key]["num_relation_groups"] = len(group_ids)

    files_index_path = root / "data" / "indices" / "files_index.csv"
    files_index_path.parent.mkdir(parents=True, exist_ok=True)
    files_rows = []
    for payload in objects.values():
        object_path = Path(payload["object_path"])
        try:
            object_path_value = str(object_path.relative_to(root))
        except ValueError:
            object_path_value = str(object_path)
        files_rows.append(
            {
                **payload,
                "object_path": object_path_value,
                "source_urls": "|".join(sorted(payload["source_urls"])),
            }
        )
    with files_index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(files_rows[0].keys()) if files_rows else [])
        if files_rows:
            writer.writeheader()
            writer.writerows(sorted(files_rows, key=lambda row: (row["olympiad_family"], row["year"] or 0, row["representative_filename"])))

    olympiads_index_path = root / "data" / "indices" / "olympiads_index.csv"
    with olympiads_index_path.open("w", encoding="utf-8", newline="") as handle:
        rows = sorted(olympiad_index.values(), key=lambda row: (row["olympiad_family"], row["year"] or 0, row["stage_or_round"]))
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)

    coverage_path = root / "data" / "indices" / "coverage_report.md"
    with coverage_path.open("w", encoding="utf-8") as handle:
        handle.write("# Coverage Report\n\n")
        by_family = defaultdict(list)
        for row in sorted(olympiad_index.values(), key=lambda row: (row["olympiad_family"], row["year"] or 0, row["stage_or_round"])):
            by_family[row["olympiad_family"]].append(row)

        entries_by_family = defaultdict(list)
        for entry in entries:
            entries_by_family[entry["olympiad_family"]].append(entry)

        if families:
            coverage_families = [family for family in PRIORITY_FAMILIES if family in families]
            coverage_families.extend(sorted(families - set(PRIORITY_FAMILIES)))
        else:
            coverage_families = PRIORITY_FAMILIES

        for family in coverage_families:
            family_rows = by_family.get(family, [])
            handle.write(f"## {family}\n\n")
            if not family_rows:
                handle.write("- No materials discovered yet.\n\n")
                continue

            years = sorted({row["year"] for row in family_rows if row["year"] is not None})
            tasks_years = sorted({row["year"] for row in family_rows if row["has_tasks"] and row["year"] is not None})
            solutions_years = sorted(
                {row["year"] for row in family_rows if row["has_solutions"] and row["year"] is not None}
            )
            mirror_only = sorted(
                {
                    entry["year"]
                    for entry in entries_by_family[family]
                    if entry["source_role"] == "mirror"
                    and entry["year"] is not None
                }
            )
            low_conf = sorted(
                {
                    entry["year"]
                    for entry in entries_by_family[family]
                    if float(entry.get("confidence", 0.0)) < 0.75 and entry["year"] is not None
                }
            )
            relation_counts = Counter(
                entry["relation_type"]
                for entry in entries_by_family[family]
                if entry.get("relation_type")
            )
            missing_rows = missing_rows_by_family.get(family, [])
            missing_years = sorted({row["year"] for row in missing_rows if row["year"] is not None})
            missing_by_doc = Counter(row["document_type"] for row in missing_rows)

            handle.write(f"- Years found: {', '.join(map(str, years))}\n")
            handle.write(f"- Years with tasks: {', '.join(map(str, tasks_years))}\n")
            handle.write(f"- Years with solutions: {', '.join(map(str, solutions_years))}\n")
            handle.write(f"- Years with mirror material: {', '.join(map(str, mirror_only)) or 'none'}\n")
            handle.write(
                "- Relation groups summary: "
                + (", ".join(f"{name}={count}" for name, count in sorted(relation_counts.items())) or "none")
                + "\n"
            )
            handle.write(f"- Low-confidence years: {', '.join(map(str, low_conf)) or 'none'}\n")
            handle.write(
                "- Discovery-only / undownloaded years: "
                + (", ".join(map(str, missing_years)) if missing_years else "none")
                + "\n"
            )
            handle.write(
                "- Undownloaded document types: "
                + (", ".join(f"{doc_type}={count}" for doc_type, count in sorted(missing_by_doc.items())) or "none")
                + "\n"
            )

            missing = []
            if years:
                for year in range(min(years), max(years) + 1):
                    if year not in years:
                        missing.append(str(year))
            handle.write(f"- Gaps: {', '.join(missing) or 'none observed inside discovered range'}\n\n")

    logger.info("INDICES files=%s olympiad_rows=%s", len(files_rows), len(olympiad_index))
    return 0


def main() -> int:
    parser = build_common_parser("Build indices and coverage report from normalized archive.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return build(args.root, families)


if __name__ == "__main__":
    raise SystemExit(main())

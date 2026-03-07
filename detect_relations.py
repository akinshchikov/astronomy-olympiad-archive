from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from utils.cli import build_common_parser
from utils.fs_utils import load_jsonl, write_json, write_jsonl
from utils.logging_utils import configure_logger
from utils.metadata import SOURCE_ROLE_RANK, path_slug, year_tag

EVENT_RELATIONS_FILENAME = "event-relations.json"


def token_set(entry: dict) -> set[str]:
    text = " ".join(
        [
            str(entry.get("source_title", "")),
            str(entry.get("filename_original", "")),
            str(entry.get("filename_normalized", "")),
            str(entry.get("source_url", "")),
            str(entry.get("notes", "")),
        ]
    ).lower()
    return {token for token in text.replace("/", " ").replace("_", " ").replace("-", " ").split() if len(token) > 2}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def classify_pair(left: dict, right: dict) -> tuple[str, float, float]:
    same_event_conf = 0.0
    if left["olympiad_family"] == right["olympiad_family"]:
        same_event_conf += 0.3
    if left["year"] == right["year"]:
        same_event_conf += 0.3
    if left["stage_or_round"] == right["stage_or_round"]:
        same_event_conf += 0.25
    if left["document_type"] == right["document_type"]:
        same_event_conf += 0.15

    if left["sha256"] == right["sha256"]:
        return "exact_duplicate", round(same_event_conf, 2), 1.0

    left_tokens = token_set(left)
    right_tokens = token_set(right)
    token_similarity = jaccard(left_tokens, right_tokens)

    size_left = int(left.get("file_size", 0) or 0)
    size_right = int(right.get("file_size", 0) or 0)
    size_similarity = 0.0
    if size_left and size_right:
        ratio = min(size_left, size_right) / max(size_left, size_right)
        size_similarity = round(ratio, 2)

    same_content_conf = round((token_similarity * 0.7) + (size_similarity * 0.3), 2)

    if left["language"] != right["language"] and same_event_conf >= 0.8:
        return "translated_version", round(same_event_conf, 2), same_content_conf
    if "scan" in left["variant_tag"] or "scan" in right["variant_tag"]:
        return "scan_variant", round(same_event_conf, 2), same_content_conf
    if left["extension"] != right["extension"] and same_event_conf >= 0.8:
        return "reformatted_version", round(same_event_conf, 2), same_content_conf
    if "annotated" in left["variant_tag"] or "annotated" in right["variant_tag"]:
        return "annotated_version", round(same_event_conf, 2), same_content_conf
    if same_event_conf >= 0.8 and same_content_conf >= 0.72:
        return "source_variant", round(same_event_conf, 2), same_content_conf
    if same_event_conf >= 0.8 and ("combined" in left["variant_tag"] or "combined" in right["variant_tag"]):
        return "partial_overlap", round(same_event_conf, 2), same_content_conf
    if same_event_conf >= 0.7 and same_content_conf >= 0.45:
        return "possible_duplicate", round(same_event_conf, 2), same_content_conf
    return "unrelated", round(same_event_conf, 2), same_content_conf


def choose_canonical(entries: list[dict]) -> dict:
    def sort_key(entry: dict) -> tuple:
        return (
            SOURCE_ROLE_RANK.get(entry["source_role"], 0),
            1 if entry["document_type"] != "info" else 0,
            int(entry.get("file_size", 0) or 0),
            1 if entry["extension"] == "pdf" else 0,
            -len(entry["filename_normalized"]),
        )

    return max(entries, key=sort_key)


def detect(root: Path, families: set[str] | None) -> int:
    logger = configure_logger("detect_relations", root / "data" / "logs" / "normalization.log")
    entries = load_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl")
    if families:
        entries = [row for row in entries if row["olympiad_family"] in families]

    buckets: dict[tuple[str, int | None, str, str], list[dict]] = defaultdict(list)
    for entry in entries:
        key = (
            entry["olympiad_family"],
            entry["year"],
            entry["stage_or_round"],
            entry["document_type"],
        )
        buckets[key].append(entry)

    relation_rows: list[dict] = []
    relation_groups: list[dict] = []
    group_counter = 1

    for bucket_entries in buckets.values():
        if len(bucket_entries) < 2:
            continue

        group_id = f"rg_{group_counter:04d}"
        bucket_relations = []
        for index, left in enumerate(bucket_entries):
            for right in bucket_entries[index + 1 :]:
                relation_type, same_event_conf, same_content_conf = classify_pair(left, right)
                if relation_type == "unrelated":
                    continue
                relation = {
                    "relation_group_id": group_id,
                    "left_candidate_id": left["candidate_id"],
                    "right_candidate_id": right["candidate_id"],
                    "olympiad_family": left["olympiad_family"],
                    "year": left["year"],
                    "stage_or_round": left["stage_or_round"],
                    "document_type": left["document_type"],
                    "relation_type": relation_type,
                    "relation_confidence": round((same_event_conf + same_content_conf) / 2, 2),
                    "same_event_confidence": same_event_conf,
                    "same_content_confidence": same_content_conf,
                }
                relation_rows.append(relation)
                bucket_relations.append(relation)

        if not bucket_relations:
            continue

        canonical = choose_canonical(bucket_entries)
        relation_summary = {}
        for relation in bucket_relations:
            relation_summary[relation["relation_type"]] = relation_summary.get(relation["relation_type"], 0) + 1

        relation_groups.append(
            {
                "relation_group_id": group_id,
                "olympiad_family": canonical["olympiad_family"],
                "year": canonical["year"],
                "stage_or_round": canonical["stage_or_round"],
                "document_type": canonical["document_type"],
                "num_variants": len(bucket_entries),
                "canonical_filename": canonical["filename_normalized"],
                "relation_summary": ", ".join(
                    f"{relation_type}:{count}" for relation_type, count in sorted(relation_summary.items())
                ),
            }
        )

        candidate_ids_in_group = {
            relation["left_candidate_id"] for relation in bucket_relations
        } | {relation["right_candidate_id"] for relation in bucket_relations}
        for entry in bucket_entries:
            if entry["candidate_id"] not in candidate_ids_in_group:
                continue
            entry["relation_group_id"] = group_id
            entry["canonical_candidate"] = entry["candidate_id"] == canonical["candidate_id"]
            best_relation = max(
                (
                    relation
                    for relation in bucket_relations
                    if relation["left_candidate_id"] == entry["candidate_id"]
                    or relation["right_candidate_id"] == entry["candidate_id"]
                ),
                key=lambda relation: relation["relation_confidence"],
            )
            entry["relation_type"] = best_relation["relation_type"]
            entry["relation_confidence"] = best_relation["relation_confidence"]
            entry["same_event_confidence"] = best_relation["same_event_confidence"]
            entry["same_content_confidence"] = best_relation["same_content_confidence"]

        group_counter += 1

    write_jsonl(root / "data" / "manifests" / "normalized_entries.jsonl", entries)
    write_jsonl(root / "data" / "manifests" / "relation_edges.jsonl", relation_rows)

    relation_groups_path = root / "data" / "indices" / "relation_groups.csv"
    relation_groups_path.parent.mkdir(parents=True, exist_ok=True)
    with relation_groups_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(relation_groups[0].keys()) if relation_groups else [])
        if relation_groups:
            writer.writeheader()
            writer.writerows(relation_groups)

    event_relations: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for relation in relation_rows:
        event_relations[
            (
                relation["olympiad_family"],
                year_tag(relation["year"]),
                relation["stage_or_round"],
            )
        ].append(relation)

    for (family, year, stage), relations in event_relations.items():
        info_dir = (
            root
            / "data"
            / "archive"
            / path_slug(family, fallback="olympiad")
            / year
            / path_slug(stage, fallback="stage")
            / "info"
        )
        if info_dir.exists():
            write_json(info_dir / EVENT_RELATIONS_FILENAME, relations)

    logger.info("RELATIONS groups=%s edges=%s", len(relation_groups), len(relation_rows))
    return 0


def main() -> int:
    parser = build_common_parser("Detect exact and near-duplicate relations among normalized files.")
    args = parser.parse_args()
    families = set(args.families) if args.families else None
    return detect(args.root, families)


if __name__ == "__main__":
    raise SystemExit(main())

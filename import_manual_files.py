from __future__ import annotations

"""Import explicitly documented local OWAO files into the normal download manifest."""

import argparse
import hashlib
from pathlib import Path

from utils.fs_utils import load_jsonl, write_jsonl
from utils.metadata import infer_extension, source_domain


REQUIRED_FIELDS = {
    "source_url", "olympiad_family", "year", "stage_or_round", "round_detail",
    "document_type", "language", "variant_tag", "filename_original", "local_path",
}


def import_manual_files(root: Path, families: set[str] | None = None) -> int:
    if families is not None and "owao" not in families:
        return 0
    manual_root = root / "data" / "manual" / "owao"
    manifest_path = manual_root / "manual_manifest.jsonl"
    if not manifest_path.exists():
        return 0

    existing = load_jsonl(root / "data" / "manifests" / "download_manifest.jsonl")
    imported: list[dict] = []
    for row in load_jsonl(manifest_path):
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"manual OWAO manifest row missing fields: {', '.join(sorted(missing))}")
        if row["olympiad_family"] != "owao":
            raise ValueError("manual import only accepts olympiad_family=owao")
        local_path = (manual_root / str(row["local_path"])).resolve()
        if manual_root.resolve() not in local_path.parents or not local_path.is_file():
            raise ValueError(f"manual local_path must name an existing file below {manual_root}: {row['local_path']}")
        source_url = str(row["source_url"])
        candidate_id = hashlib.sha1(f"owao_tasks_official::{source_url}".encode("utf-8")).hexdigest()
        imported.append({
            **row,
            "candidate_id": candidate_id,
            "source_id": "owao_tasks_official",
            "source_domain": source_domain(source_url),
            "source_title": str(row["filename_original"]),
            "source_priority": 1,
            "source_role": "official",
            "parent_page_url": source_url,
            "parent_page_title": "manual OWAO import",
            "extension": infer_extension(str(local_path)),
            "notes": "official; manual_import=true",
            "seed_context": {},
            "raw_path": str(local_path),
            "txt_path": "",
            "status": "manual",
            "content_type": "",
        })
    imported_ids = {row["candidate_id"] for row in imported}
    write_jsonl(root / "data" / "manifests" / "download_manifest.jsonl", [
        row for row in existing if row.get("candidate_id") not in imported_ids
    ] + imported)
    return len(imported)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import manually downloaded OWAO files into download_manifest.jsonl.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(f"Imported {import_manual_files(args.root)} manual OWAO file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

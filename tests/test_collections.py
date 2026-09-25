from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import build_indices
from utils.fs_utils import write_jsonl


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class CollectionIndexTests(TestCase):
    def test_collections_are_indexed_without_creating_olympiad_events(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manifests = root / "data" / "manifests"
            manifests.mkdir(parents=True)
            collection = {
                "candidate_id": "collection-1",
                "source_id": "official-collection",
                "source_url": "https://example.test/collection.pdf",
                "source_role": "official",
                "olympiad_family": "example",
                "year": None,
                "stage_or_round": "collection",
                "document_type": "solutions",
                "logical_document_types": ["tasks", "solutions"],
                "language": "en",
                "confidence": 0.99,
                "record_kind": "collection",
                "collection_id": "example-collection",
                "collection_title": "Example problems and solutions",
                "collection_type": "competition_compilation",
                "publication_year": 2025,
                "covered_years": "2010-2024",
                "related_families": ["example"],
                "access_mode": "download",
                "sha256": "a" * 64,
                "object_path": str(root / "data" / "archive" / "objects" / ("a" * 64 + ".pdf")),
                "extension": "pdf",
                "file_size": 123,
                "filename_normalized": "example-collection.pdf",
            }
            event = {
                "candidate_id": "event-1",
                "source_id": "official-event",
                "source_url": "https://example.test/2025.pdf",
                "source_role": "official",
                "olympiad_family": "example",
                "year": 2025,
                "stage_or_round": "final",
                "document_type": "tasks",
                "logical_document_types": ["tasks"],
                "language": "en",
                "confidence": 0.9,
                "sha256": "b" * 64,
                "object_path": str(root / "data" / "archive" / "objects" / ("b" * 64 + ".pdf")),
                "extension": "pdf",
                "file_size": 456,
                "filename_normalized": "2025-example-final-tasks.pdf",
            }
            write_jsonl(manifests / "normalized_entries.jsonl", [collection, event])
            write_jsonl(manifests / "discovered_documents.jsonl", [collection, event])
            write_jsonl(manifests / "download_manifest.jsonl", [collection, event])

            self.assertEqual(build_indices.build(root, None), 0)

            olympiads = csv_rows(root / "data" / "indices" / "olympiads_index.csv")
            self.assertEqual(len(olympiads), 1)
            self.assertEqual((olympiads[0]["year"], olympiads[0]["stage_or_round"]), ("2025", "final"))

            collections = csv_rows(root / "data" / "indices" / "collections_index.csv")
            self.assertEqual(len(collections), 1)
            self.assertEqual(collections[0]["collection_id"], "example-collection")
            self.assertEqual(collections[0]["covered_years"], "2010-2024")
            self.assertEqual(collections[0]["document_types"], "solutions|tasks")
            self.assertEqual(collections[0]["downloaded_files"], "1")

            files = csv_rows(root / "data" / "indices" / "files_index.csv")
            self.assertEqual(len(files), 2)
            collection_file = next(row for row in files if row["record_kind"] == "collection")
            self.assertEqual(collection_file["collection_id"], "example-collection")

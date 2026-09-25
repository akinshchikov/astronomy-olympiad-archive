from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import build_indices
import discover_sources
from utils.fs_utils import load_jsonl, write_jsonl
from utils.source_configs import SOURCE_DEFINITIONS, iter_seed_requests


COLLECTION_SOURCE_IDS = {
    "slovakia_astronomy_official_materials",
    "mao_collection_1997_2002",
    "mao_collection_2003_2005",
    "mao_collection_2006_2015",
    "ioaa_problem_collection_official",
    "poland_astronomy_preparation_official",
    "caao_tutorials_official",
    "usaaao_training_resources",
    "singapore_astronomy_training_resources",
}


class PublicCollectionTests(TestCase):
    def test_public_collection_sources_are_configured_without_purchase_targets(self) -> None:
        by_id = {source.source_id: source for source in SOURCE_DEFINITIONS}
        self.assertLessEqual(COLLECTION_SOURCE_IDS, set(by_id))
        self.assertIn("slovakia_astronomy_official_archive", by_id)

        purchase_tokens = ("ozon.", "amazon.", "market.yandex", "bookstore", "shop.")
        for source_id in COLLECTION_SOURCE_IDS:
            source = by_id[source_id]
            targets = [*source.seed_urls, *source.extras.get("direct_file_urls", [])]
            with self.subTest(source_id=source_id):
                self.assertFalse(any(token in url.lower() for url in targets for token in purchase_tokens))
                if source.strategy == "direct_files":
                    self.assertEqual(iter_seed_requests(source), [])
                    self.assertTrue(source.extras.get("direct_file_urls"))

    def test_collection_context_is_promoted_to_discovery_metadata(self) -> None:
        source = next(source for source in SOURCE_DEFINITIONS if source.source_id == "ioaa_problem_collection_official")
        href = source.extras["direct_file_urls"][0]
        context = dict(source.extras["default_context"])
        seed = {
            "source_id": source.source_id,
            "olympiad_family": source.olympiad_family,
            "source_role": source.source_role,
            "source_priority": source.source_priority,
            "context": context,
        }
        row = discover_sources.build_candidate_entry(
            seed,
            href=href,
            link_text="IOAA problems and solutions 2007-2025",
            page_title=source.label,
            parent_page_url=source.seed_urls[0],
            parent_page_title=source.label,
            context=context,
        )
        self.assertEqual(row["material_scope"], "collection")
        self.assertEqual(row["collection_id"], "ioaa_problem_collection_2007_2025")
        self.assertEqual(row["stage_or_round"], "collection")
        self.assertEqual(set(row["logical_document_types"]), {"tasks", "solutions"})

    def test_slovak_archive_filename_metadata(self) -> None:
        seed = {
            "source_id": "slovakia_astronomy_official_archive",
            "olympiad_family": "slovakia_astronomy",
            "source_role": "official",
            "source_priority": 1,
            "context": {},
        }
        row = discover_sources.build_candidate_entry(
            seed,
            href="https://www.astronomickaolympiada.sk/wp-content/uploads/2025/05/AO-2025-CK-SS-Riesenia-1.pdf",
            link_text="AO-2025-CK-SS-Riesenia",
            page_title="Archív úloh",
            parent_page_url="https://www.astronomickaolympiada.sk/ulohy/archiv-uloh/",
            parent_page_title="Archív úloh",
            context={},
        )
        self.assertEqual(
            (row["year"], row["stage_or_round"], row["document_type"], row["round_detail"], row["language"]),
            (2025, "final", "solutions", "secondary", "sk"),
        )

    def test_collection_rows_do_not_create_olympiad_events(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            event = {
                "candidate_id": "event",
                "source_id": "event_source",
                "olympiad_family": "test_family",
                "year": 2025,
                "stage_or_round": "final",
                "document_type": "tasks",
                "logical_document_types": ["tasks"],
                "language": "en",
                "source_url": "https://example.test/event.pdf",
                "source_role": "official",
                "confidence": 0.9,
                "sha256": "a" * 64,
                "object_path": str(root / "data/archive/objects/event.pdf"),
                "extension": "pdf",
                "file_size": 10,
                "filename_normalized": "event.pdf",
                "relation_group_id": "",
                "relation_type": "",
                "seed_context": {},
            }
            collection = {
                "candidate_id": "collection",
                "source_id": "collection_source",
                "olympiad_family": "test_family",
                "year": 2026,
                "stage_or_round": "collection",
                "document_type": "solutions",
                "logical_document_types": ["tasks", "solutions"],
                "language": "en",
                "source_url": "https://example.test/collection.pdf",
                "source_role": "official",
                "confidence": 0.9,
                "sha256": "b" * 64,
                "object_path": str(root / "data/archive/objects/collection.pdf"),
                "extension": "pdf",
                "file_size": 20,
                "filename_normalized": "collection.pdf",
                "relation_group_id": "",
                "relation_type": "",
                "material_scope": "collection",
                "collection_id": "test_collection",
                "collection_title": "Test collection",
                "collection_type": "competition_compilation",
                "covered_years": "2020-2025",
                "publication_year": 2026,
                "seed_context": {
                    "material_scope": "collection",
                    "collection_id": "test_collection",
                    "collection_title": "Test collection",
                    "collection_type": "competition_compilation",
                    "covered_years": "2020-2025",
                    "publication_year": 2026,
                },
            }
            discovered = [
                {key: value for key, value in event.items() if key not in {"sha256", "object_path", "file_size", "filename_normalized", "relation_group_id", "relation_type"}},
                {key: value for key, value in collection.items() if key not in {"sha256", "object_path", "file_size", "filename_normalized", "relation_group_id", "relation_type"}},
            ]
            write_jsonl(root / "data/manifests/normalized_entries.jsonl", [event, collection])
            write_jsonl(root / "data/manifests/discovered_documents.jsonl", discovered)
            write_jsonl(
                root / "data/manifests/download_manifest.jsonl",
                [
                    {"candidate_id": "event", "olympiad_family": "test_family"},
                    {"candidate_id": "collection", "olympiad_family": "test_family"},
                ],
            )
            (root / "data/config").mkdir(parents=True, exist_ok=True)
            (root / "data/config/family_metadata.csv").write_text(
                "family_id,name_en,name_ru,region,competition_scope\n"
                "test_family,Test family,Тестовая олимпиада,Test,national\n",
                encoding="utf-8",
            )
            (root / "data/audits").mkdir(parents=True, exist_ok=True)
            (root / "data/audits/source_coverage.csv").write_text(
                "family,source_id,configured,source_role,safe_seed_url,content_state,completeness,access_state,redistribution_status,live_check_result,evidence,parser_notes\n",
                encoding="utf-8",
            )

            self.assertEqual(build_indices.build(root, None), 0)

            with (root / "data/indices/olympiads_index.csv").open(encoding="utf-8", newline="") as handle:
                olympiad_rows = list(csv.DictReader(handle))
            with (root / "data/indices/collections_index.csv").open(encoding="utf-8", newline="") as handle:
                collection_rows = list(csv.DictReader(handle))

            self.assertEqual([(row["year"], row["stage_or_round"]) for row in olympiad_rows], [("2025", "final")])
            self.assertEqual(len(collection_rows), 1)
            self.assertEqual(collection_rows[0]["collection_id"], "test_collection")
            self.assertEqual(collection_rows[0]["num_files"], "1")
            self.assertEqual(collection_rows[0]["has_tasks"], "True")
            self.assertEqual(collection_rows[0]["has_solutions"], "True")

from pathlib import Path
from unittest import TestCase

import crawl_source
import discover_sources
from utils.source_configs import SOURCE_DEFINITIONS, iter_seed_requests


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "russia_correspondence_preserved_publication"


class PreservedPublicationTests(TestCase):
    def source(self):
        return next(source for source in SOURCE_DEFINITIONS if source.source_id == SOURCE_ID)

    def test_preserved_source_has_no_network_seed(self):
        source = self.source()
        self.assertEqual(source.strategy, "preserved")
        self.assertEqual(iter_seed_requests(source), [])

    def test_russian_correspondence_manifest_is_bounded_and_integral(self):
        rows = discover_sources.preserved_source_entries(ROOT, self.source())
        self.assertEqual([row["year"] for row in rows], [2005, 2006, 2007, 2008])
        self.assertEqual({row["stage_or_round"] for row in rows}, {"correspondence"})
        self.assertEqual({row["document_type"] for row in rows}, {"tasks"})
        self.assertTrue(all(row["logical_document_types"] == ["tasks", "solutions"] for row in rows))
        self.assertTrue(all(row["language"] == "ru" for row in rows))
        self.assertTrue(all(row["redistribution_status"] == "explicit-permission" for row in rows))
        self.assertTrue(all(row["access_mode"] == "repository_preserved" for row in rows))

    def test_preserved_files_are_valid_local_download_inputs(self):
        rows = discover_sources.preserved_source_entries(ROOT, self.source())
        for row in rows:
            with self.subTest(year=row["year"]):
                record = crawl_source.preserved_repository_download_record(ROOT, row, row["extension"])
                self.assertIsNotNone(record)
                assert record is not None
                self.assertEqual(record["status"], "preserved")
                self.assertEqual(record["content_type"], "application/pdf")
                self.assertEqual(record["bytes"], row["expected_bytes"])
                self.assertTrue(Path(record["raw_path"]).is_file())

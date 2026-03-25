from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import cleanup_outputs


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


class CleanupOutputsTests(TestCase):
    def test_full_clean_removes_generated_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            touch(root / "data" / "raw" / "spbao_official" / "a.bin")
            touch(root / "data" / "archive" / "spbao" / "2025" / "final" / "tasks" / "file.pdf")
            touch(root / "data" / "archive" / "objects" / "sha256.pdf")
            touch(root / "data" / "logs" / "download.log")
            touch(root / "data" / "manifests" / "download_manifest.jsonl")
            touch(root / "data" / "indices" / "files_index.csv")

            cleanup_outputs.clean_outputs(root, families=None)

            self.assertFalse((root / "data" / "raw").exists())
            self.assertFalse((root / "data" / "archive").exists())
            self.assertFalse((root / "data" / "logs").exists())
            self.assertFalse((root / "data" / "manifests" / "download_manifest.jsonl").exists())
            self.assertFalse((root / "data" / "indices" / "files_index.csv").exists())

    def test_family_clean_removes_only_selected_family_outputs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            touch(root / "data" / "raw" / "spbao_official" / "a.bin")
            touch(root / "data" / "raw" / "spbao_olimpiada_archive" / "b.html")
            touch(root / "data" / "raw" / "spbao_year_class_pages" / "c.html")
            touch(root / "data" / "raw" / "iao_eaae_index" / "d.html")
            touch(root / "data" / "archive" / "spbao" / "2025" / "final" / "tasks" / "file.pdf")
            touch(root / "data" / "archive" / "iao" / "1999" / "theoretical" / "tasks" / "file.html")
            touch(root / "data" / "archive" / "objects" / "shared.pdf")
            touch(root / "data" / "logs" / "download.log")
            touch(root / "data" / "manifests" / "download_manifest.jsonl")
            touch(root / "data" / "indices" / "files_index.csv")

            cleanup_outputs.clean_outputs(root, families={"spbao"})

            self.assertFalse((root / "data" / "raw" / "spbao_official").exists())
            self.assertFalse((root / "data" / "raw" / "spbao_olimpiada_archive").exists())
            self.assertFalse((root / "data" / "raw" / "spbao_year_class_pages").exists())
            self.assertFalse((root / "data" / "archive" / "spbao").exists())
            self.assertFalse((root / "data" / "logs").exists())

            self.assertTrue((root / "data" / "raw" / "iao_eaae_index").exists())
            self.assertTrue((root / "data" / "archive" / "iao").exists())
            self.assertTrue((root / "data" / "archive" / "objects").exists())
            self.assertTrue((root / "data" / "manifests" / "download_manifest.jsonl").exists())
            self.assertTrue((root / "data" / "indices" / "files_index.csv").exists())

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import detect_relations
import run_pipeline


class PublicSnapshotProtectionTests(TestCase):
    def test_focused_snapshot_guard_restores_files_byte_for_byte(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            expected: dict[str, bytes] = {}
            for index, relative in enumerate(run_pipeline.PUBLIC_SNAPSHOT_FILES):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                payload = f"snapshot-{index}\r\n".encode()
                path.write_bytes(payload)
                expected[relative] = payload

            with run_pipeline.preserve_public_snapshot(root, enabled=True):
                for relative in run_pipeline.PUBLIC_SNAPSHOT_FILES:
                    (root / relative).write_bytes(b"focused-output\n")

            for relative, payload in expected.items():
                self.assertEqual((root / relative).read_bytes(), payload)

    def test_focused_snapshot_guard_removes_new_public_file_when_original_was_absent(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            relative = run_pipeline.PUBLIC_SNAPSHOT_FILES[0]
            path = root / relative
            with run_pipeline.preserve_public_snapshot(root, enabled=True):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("temporary", encoding="utf-8")
            self.assertFalse(path.exists())

    def test_relation_group_id_is_stable_and_bucket_derived(self) -> None:
        key = ("czech_astronomy", 2020, "regional", "solutions")
        self.assertEqual(
            detect_relations.relation_group_id_for_bucket(key),
            "rg--czech-astronomy--2020--regional--solutions",
        )
        self.assertEqual(
            detect_relations.relation_group_id_for_bucket(("iao", None, "theoretical", "tasks")),
            "rg--iao--unknown-year--theoretical--tasks",
        )
        self.assertNotEqual(
            detect_relations.relation_group_id_for_bucket(key),
            detect_relations.relation_group_id_for_bucket(("czech_astronomy", 2021, "regional", "solutions")),
        )

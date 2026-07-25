import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase


SCRIPT = Path(__file__).parents[1] / "scripts" / "refresh_source_expansion.sh"
PROTECTED = (
    "data/manifests/discovered_documents.jsonl",
    "data/manifests/discovery_coverage.csv",
    "data/indices/olympiads_index.csv",
    "data/indices/coverage_report.md",
    "data/indices/files_index.csv",
    "data/indices/relation_groups.csv",
)


class RefreshScriptTests(TestCase):
    def make_repo(self, root: Path, discovery: str, build: str, old_rows=None) -> dict[str, Path]:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "scripts").mkdir()
        (root / "data/manifests").mkdir(parents=True)
        (root / "data/indices").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "tests/test_placeholder.py").write_text("import unittest\n\nclass Placeholder(unittest.TestCase):\n    def test_stage(self):\n        self.assertTrue(True)\n")
        shutil.copy2(SCRIPT, root / "scripts/refresh_source_expansion.sh")
        (root / "discover_sources.py").write_text(discovery)
        (root / "build_indices.py").write_text(build)
        old_rows = old_rows or [{"olympiad_family": "struve"}]
        (root / "data/manifests/discovered_documents.jsonl").write_text("\n".join(json.dumps(row) for row in old_rows) + "\n")
        (root / "data/manifests/discovery_coverage.csv").write_text("old\n")
        (root / "data/manifests/normalized_entries.jsonl").write_text("{}\n")
        (root / "data/manifests/relation_edges.jsonl").write_text("{}\n")
        (root / "data/manifests/source_candidates.csv").write_text(
            "source_id,olympiad_family,source_role,source_priority\n"
            "legacy_iao,iao,archive,2\n"
        )
        for name in ("olympiads_index.csv", "coverage_report.md", "files_index.csv", "relation_groups.csv"):
            (root / "data/indices" / name).write_text(f"original-{name}\n")
        return {relative: root / relative for relative in PROTECTED}

    def run_script(self, root: Path, **environment: str) -> subprocess.CompletedProcess[str]:
        env = os.environ | environment
        return subprocess.run([str(root / "scripts/refresh_source_expansion.sh")], cwd=root, text=True, capture_output=True, env=env)

    def valid_rows(self) -> list[dict]:
        return [
            {"olympiad_family": "struve", "source_id": "struve_astroedu_archive", "year": 2026, "stage_or_round": "final", "round_detail": "written", "access_mode": "download"},
            *[{"olympiad_family": "struve", "source_domain": "uts.astroedu.ru", "stage_or_round": "regional", "round_detail": "online", "access_mode": "discovery_only", "year": year} for year in (2023, 2024, 2025, 2026)],
            {"olympiad_family": "mao", "source_id": "mao_official_archive", "year": 2026},
            {"olympiad_family": "russia_team_qual", "source_domain": "uts.astroedu.ru", "access_mode": "discovery_only", "round_detail": "Q26S1"},
            {"olympiad_family": "iao", "source_domain": "issp.ac.ru", "source_role": "official", "notes": "discovered_via=iao_eaae_index"},
        ]

    def discovery_program(self, rows: list[dict]) -> str:
        return """import json
from pathlib import Path
rows = %r
Path('data/manifests/discovered_documents.jsonl').write_text('\\n'.join(json.dumps(row) for row in rows) + '\\n')
Path('data/manifests/discovery_coverage.csv').write_text('generated-coverage\\n')
Path('data/manifests/source_candidates.csv').write_text('source_id,olympiad_family,source_role,source_priority\\nstruve_astroedu_archive,struve,official,1\\nstruve_moscow_year_pages,struve,mirror,2\\nmao_official_archive,mao,official,1\\nmao_moscow_archive,mao,archive,2\\n')
""" % rows

    def build_program(self, *, semantic_failure: bool = False) -> str:
        report = "wrong report\n" if semantic_failure else "Known not-held components: 2022 final\n## iao\nGaps: none\n## ioaa\nGaps: none\n## end\n"
        return """from pathlib import Path
Path('data/indices/olympiads_index.csv').write_text('olympiad_family,year,has_tasks,has_solutions\\nmao,2026,True,True\\nserbia_astronomy,2026,True,True\\n')
Path('data/indices/coverage_report.md').write_text(%r)
""" % report

    def snapshot(self, paths: dict[str, Path]) -> dict[str, bytes]:
        return {relative: path.read_bytes() for relative, path in paths.items()}

    def test_struve_validation_failure_after_staged_write_preserves_all_protected_files(self):
        rows = [row for row in self.valid_rows() if row.get("year") != 2026 or row.get("source_domain") != "uts.astroedu.ru"]
        with TemporaryDirectory() as tmp:
            paths = self.make_repo(Path(tmp), self.discovery_program(rows), self.build_program())
            before = self.snapshot(paths)
            result = self.run_script(Path(tmp))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Struve regional-online UTS coverage missing years: [2026]", result.stdout)
            self.assertEqual(before, self.snapshot(paths))

    def test_truncated_discovery_preserves_all_protected_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_repo(root, "from pathlib import Path\nPath('data/manifests/discovered_documents.jsonl').write_text('')\n", self.build_program())
            before = self.snapshot(paths)
            result = self.run_script(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(before, self.snapshot(paths))

    def test_semantic_index_failure_preserves_all_protected_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_repo(root, self.discovery_program(self.valid_rows()), self.build_program(semantic_failure=True))
            before = self.snapshot(paths)
            result = self.run_script(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Struve not-held validation failed", result.stdout)
            self.assertEqual(before, self.snapshot(paths))

    def test_final_install_failure_rolls_back_every_protected_file(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_repo(root, self.discovery_program(self.valid_rows()), self.build_program())
            before = self.snapshot(paths)
            result = self.run_script(root, REFRESH_FAIL_AFTER_INSTALL_COUNT="2")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("INTERNAL TRANSACTION VIOLATION", result.stdout)
            self.assertEqual(before, self.snapshot(paths))

    def test_success_changes_only_four_intended_outputs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_repo(root, self.discovery_program(self.valid_rows()), self.build_program())
            before = self.snapshot(paths)
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            after = self.snapshot(paths)
            for relative in PROTECTED[:4]:
                self.assertNotEqual(before[relative], after[relative])
            for relative in PROTECTED[4:]:
                self.assertEqual(before[relative], after[relative])

    def test_legacy_source_id_family_accounting_is_complete(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_repo(root, self.discovery_program(self.valid_rows()), self.build_program(), old_rows=[{"source_id": "legacy_iao"}])
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Old total=1 new total=8 classified old=1 unclassified old=0", result.stdout)
            self.assertIn("iao: 1 -> 1", result.stdout)
            self.assertEqual(paths[PROTECTED[4]].read_text(), "original-files_index.csv\n")

    def test_regional_online_uts_and_direct_final_written_are_the_required_struve_semantics(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.make_repo(root, self.discovery_program(self.valid_rows()), self.build_program())
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("final-online", result.stdout + result.stderr)
            self.assertIn("generated-coverage", paths[PROTECTED[1]].read_text())

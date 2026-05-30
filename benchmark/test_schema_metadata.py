#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeindex.ci import run_ci_check
from codeindex.doctor import inspect_repo
from codeindex.index import build
from codeindex.symbol_extractor import extract_csharp
from codeindex.symbols import build_symbol_index


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "repo_intelligence"
EXPECTED_ROOT = Path(__file__).parent / "fixtures" / "expected"


def _load_expected(name: str) -> dict:
    return json.loads((EXPECTED_ROOT / name).read_text())


class SchemaMetadataTests(unittest.TestCase):
    def assert_symbol_metadata(self, symbol: dict, expected: dict) -> None:
        self.assertEqual(symbol["analysisMode"], expected["analysisMode"])
        self.assertEqual(symbol["extractor"], expected["extractor"])
        self.assertEqual(symbol["schemaVersion"], 1)
        self.assertIn("extractorVersion", symbol)
        self.assertIn("confidence", symbol)
        self.assertGreaterEqual(symbol["confidence"], expected["confidenceMin"])
        if "confidenceMax" in expected:
            self.assertLessEqual(symbol["confidence"], expected["confidenceMax"])

    def test_symbol_index_contains_schema_and_confidence_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "service.py").write_text("class Service:\n    pass\n")
            data = build_symbol_index(str(root))

        self.assertEqual(data["schemaVersion"], 1)
        meta = data["meta"]
        self.assertEqual(meta["schemaVersion"], 1)
        self.assertIn("generatedAt", meta)
        self.assertIn("toolVersion", meta)
        self.assertEqual(meta["analysisModes"]["python"]["ast"], 1)
        self.assertGreaterEqual(meta["confidence"]["average"], 0.9)

        symbol = data["file_symbols"]["service.py"][0]
        self.assertEqual(symbol["analysisMode"], "ast")
        self.assertEqual(symbol["extractor"], "python-ast")
        self.assertIn("confidence", symbol)

    def test_codeindex_contains_additive_schema_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "service.py").write_text("import os\n")
            output = root / "index.json"
            data = build(str(root), output)
            written = json.loads(output.read_text())

        for index_data in (data, written):
            self.assertEqual(index_data["schemaVersion"], 1)
            meta = index_data["meta"]
            self.assertEqual(meta["schemaVersion"], 1)
            self.assertIn("generatedAt", meta)
            self.assertIn("toolVersion", meta)
            self.assertIn("diagnostics", meta)
            self.assertIn("analysisModes", meta)
            self.assertTrue(meta["indexed"])

    def test_doctor_reports_healthy_generated_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "service.py").write_text("class Service:\n    pass\n")
            index_path = root / "codeindex.json"
            symbol_path = root / "symbolindex.json"
            build(str(root), index_path)
            symbol_path.write_text(json.dumps(build_symbol_index(str(root))))

            report = inspect_repo(str(root), max_age_days=7)

        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["summary"]["warnings"], 0)

    def test_doctor_reports_missing_codeindex_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            report = inspect_repo(td)

        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "error")
        self.assertGreaterEqual(report["summary"]["errors"], 1)

    def test_fixture_symbol_metadata_matches_expected_truth(self) -> None:
        expected = _load_expected("symbol_metadata.json")
        with patch("codeindex.symbol_extractor._extract_csharp_roslyn", return_value=None):
            data = build_symbol_index(str(FIXTURE_ROOT))

        self.assertEqual(set(data["file_symbols"]), set(expected["files"]))
        for file_path, expected_symbols in expected["files"].items():
            by_name = {symbol["name"]: symbol for symbol in data["file_symbols"][file_path]}
            self.assertEqual(set(by_name), set(expected_symbols), file_path)
            for name, metadata in expected_symbols.items():
                self.assert_symbol_metadata(by_name[name], metadata)

        self.assertEqual(
            data["meta"]["analysisModes"],
            expected["meta"]["analysisModes"],
        )
        self.assertEqual(data["meta"]["confidence"]["bands"]["high"], 2)
        self.assertEqual(data["meta"]["confidence"]["bands"]["medium"], 16)

    def test_fixture_csharp_roslyn_and_regex_metadata_are_distinguishable(self) -> None:
        fixture = FIXTURE_ROOT / "csharp" / "Service.cs"
        with patch("codeindex.symbol_extractor._extract_csharp_roslyn", return_value=[{
            "name": "FixtureCSharpService",
            "line": 1,
            "kind": "class",
            "exported": True,
        }]):
            roslyn_symbols = extract_csharp(fixture)
        with patch("codeindex.symbol_extractor._extract_csharp_roslyn", return_value=None):
            regex_symbols = extract_csharp(fixture)

        roslyn = roslyn_symbols[0]
        regex = {symbol["name"]: symbol for symbol in regex_symbols}["FixtureCSharpService"]
        self.assertEqual(roslyn["analysisMode"], "roslyn")
        self.assertEqual(roslyn["extractor"], "codeindex-csharp-symbols")
        self.assertEqual(regex["analysisMode"], "regex")
        self.assertEqual(regex["extractor"], "csharp-regex")
        self.assertGreater(roslyn["confidence"], regex["confidence"])

    def test_legacy_indexes_warn_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            codeindex_path = root / "legacy-codeindex.json"
            symbol_path = root / "legacy-symbolindex.json"
            codeindex_path.write_text(json.dumps({
                "meta": {"languages": ["python"], "diagnostics": []},
                "nodes": [],
                "links": [],
            }))
            symbol_path.write_text(json.dumps({
                "meta": {"generated": "2026-05-30", "repo": "legacy/", "total_symbols": 0, "diagnostics": []},
                "symbols": {},
                "file_symbols": {},
            }))

            report = inspect_repo(
                str(root),
                index_path=str(codeindex_path),
                symbol_index_path=str(symbol_path),
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["status"], "warning")
        self.assertEqual(report["summary"]["errors"], 0)
        warning_names = {check["name"] for check in report["checks"] if check["status"] == "warning"}
        self.assertIn("codeindex-schema", warning_names)
        self.assertIn("codeindex-freshness", warning_names)
        self.assertIn("symbolindex-schema", warning_names)
        self.assertIn("symbolindex-freshness", warning_names)

    def test_ci_warning_policy_matches_expected_truth(self) -> None:
        expected = _load_expected("ci_policy.json")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            index_path = root / "codeindex.json"
            symbol_path = root / "symbolindex.json"
            index_path.write_text(json.dumps({
                "meta": {"languages": ["python"], "diagnostics": []},
                "nodes": [],
                "links": [],
            }))
            symbol_path.write_text(json.dumps({
                "meta": {"generated": "2026-05-30", "repo": "legacy/", "total_symbols": 0, "diagnostics": []},
                "symbols": {},
                "file_symbols": {},
            }))

            non_strict = run_ci_check(str(root), index_path=str(index_path), symbol_index_path=str(symbol_path))
            strict = run_ci_check(str(root), index_path=str(index_path), symbol_index_path=str(symbol_path), strict=True)
            missing = run_ci_check(str(root), index_path=str(root / "missing-codeindex.json"), symbol_index_path=str(symbol_path))

        self.assertEqual(non_strict["ok"], expected["nonStrictWarnings"]["ok"])
        self.assertEqual(non_strict["status"], expected["nonStrictWarnings"]["status"])
        self.assertEqual(strict["ok"], expected["strictWarnings"]["ok"])
        self.assertEqual(strict["status"], expected["strictWarnings"]["status"])
        self.assertEqual(missing["ok"], expected["missingIndex"]["ok"])
        self.assertEqual(missing["status"], expected["missingIndex"]["status"])


if __name__ == "__main__":
    unittest.main()
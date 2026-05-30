#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeindex.cli import _build_parser
from codeindex.index import build
from codeindex.symbols import build_symbol_index


class ModeContractTests(unittest.TestCase):
    def test_analyze_csharp_repo_records_requested_and_actual_roslyn_modes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Service.cs").write_text("public class Service {}\n")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.analyze", return_value=(
                [{
                    "id": "Service.cs",
                    "type": "module",
                    "language": "csharp",
                    "loc": 1,
                    "imports": 0,
                    "group": 0,
                }],
                [],
                {},
                {
                    "total_files": 1,
                    "total_loc": 1,
                    "actualModes": {"csharp": "roslyn"},
                    "diagnostics": [],
                },
            )), patch("codeindex.runtime_contract.inspect_dotnet_runtime", return_value={
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "supported": True,
                "diagnostics": [],
            }):
                data = build(str(root), first_use_budget_seconds=12.5)

        meta = data["meta"]
        self.assertEqual(meta["requestedModes"]["csharp"], "roslyn")
        self.assertEqual(meta["actualModes"]["csharp"], "roslyn")
        runtime = meta["analysisRuntime"]["csharp"]
        self.assertEqual(runtime["requestedMode"], "roslyn")
        self.assertEqual(runtime["actualMode"], "roslyn")
        self.assertEqual(runtime["helperProtocolVersion"], "1")
        self.assertEqual(runtime["dotnetPath"], "/tmp/dotnet")
        self.assertEqual(runtime["dotnetSdkVersion"], "10.0.100")
        self.assertEqual(runtime["timings"]["firstUseBudgetSeconds"], 12.5)
        self.assertEqual(runtime["diagnostics"], [])

    def test_analyze_csharp_repo_fails_actionably_when_roslyn_tooling_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Service.cs").write_text("public class Service {}\n")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "dotnetPath": None,
                "dotnetSdkVersion": None,
                "supported": False,
                "diagnostics": ["No supported dotnet SDK was found."],
            }):
                with self.assertRaisesRegex(RuntimeError, "Roslyn helper is unavailable"):
                    build(str(root), first_use_budget_seconds=12.5)

    def test_symbol_index_csharp_repo_records_roslyn_request_and_regex_actual(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Service.cs").write_text(
                "public class PublicService\n{\n    public int Run(string input) => input.Length;\n}\n"
            )
            with patch("codeindex.runtime_contract.inspect_dotnet_runtime", return_value={
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "supported": True,
                "diagnostics": [],
            }), patch("codeindex.symbol_extractor._extract_csharp_roslyn", return_value=None):
                data = build_symbol_index(str(root), first_use_budget_seconds=7.0)

        meta = data["meta"]
        self.assertEqual(meta["requestedModes"]["csharp"], "roslyn")
        self.assertEqual(meta["actualModes"]["csharp"], "regex")
        runtime = meta["analysisRuntime"]["csharp"]
        self.assertEqual(runtime["requestedMode"], "roslyn")
        self.assertEqual(runtime["actualMode"], "regex")
        self.assertEqual(runtime["timings"]["firstUseBudgetSeconds"], 7.0)
        self.assertTrue(any("actual mode is currently regex" in item for item in runtime["diagnostics"]))

    def test_cli_help_exposes_first_use_budget_flag(self) -> None:
        parser = _build_parser()
        subparsers = parser._subparsers._group_actions[0].choices
        self.assertIn("--first-use-budget-seconds", subparsers["analyze"].format_help())
        self.assertIn("--first-use-budget-seconds", subparsers["symbols"].format_help())


if __name__ == "__main__":
    unittest.main()
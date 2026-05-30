#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeindex.analyzers.csharp_analyzer_roslyn import CommandResult, analyze, extract_csharp_symbols_with_helper


def _valid_payload() -> str:
    return json.dumps({
        "schemaVersion": 1,
        "nodes": [{
            "id": "src/WidgetService.cs",
            "type": "module",
            "language": "csharp",
            "loc": 12,
            "imports": 2,
        }],
        "external_nodes": [{
            "id": "nuget:Newtonsoft.Json/13.0.3",
            "type": "package",
            "language": "csharp",
            "loc": 0,
            "imports": 0,
        }],
        "links": [{
            "source": "src/WidgetService.cs",
            "target": "nuget:Newtonsoft.Json/13.0.3",
            "weight": 1,
            "sourceSpan": {
                "startLine": 4,
                "startColumn": 9,
                "endLine": 4,
                "endColumn": 20,
            },
        }],
        "symbols": [{
            "name": "WidgetService",
            "line": 3,
            "kind": "class",
            "exported": True,
            "methods": ["Run"],
            "accessibility": "public",
            "signature": "public sealed class WidgetService",
            "sourceSpan": {
                "startLine": 3,
                "startColumn": 1,
                "endLine": 7,
                "endColumn": 2,
            },
        }],
        "meta": {
            "sdkVersion": "10.0.100",
            "helperVersion": "0.2.0",
            "helperProtocolVersion": "1",
            "diagnostics": ["helper smoke ok"],
            "timing": {"elapsedMs": 8},
        },
    })


class RoslynHelperAdapterTests(unittest.TestCase):
    def test_missing_dotnet_reports_actionable_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": False,
                "dotnetPath": None,
                "dotnetSdkVersion": None,
                "diagnostics": ["No supported dotnet SDK was found."],
            }):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNone(result.symbols)
        self.assertTrue(any("No supported dotnet SDK was found" in item for item in result.diagnostics))
        self.assertTrue(any("Helper cache path" in item for item in result.diagnostics))

    def test_restore_or_build_failure_bubbles_up(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(None, ["Roslyn helper restore failed. Cache path: /tmp/cache. boom"]),
            ):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNone(result.symbols)
        self.assertTrue(any("restore failed" in item for item in result.diagnostics))

    def test_nonzero_helper_exit_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(Path("/tmp/helper.dll"), []),
            ), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._run_command",
                return_value=CommandResult(3, "", "helper exploded", 12.0),
            ):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNone(result.symbols)
        self.assertTrue(any("non-zero status" in item for item in result.diagnostics))
        self.assertTrue(any("helper exploded" in item for item in result.diagnostics))

    def test_invalid_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(Path("/tmp/helper.dll"), []),
            ), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._run_command",
                return_value=CommandResult(0, "{\"schemaVersion\": 1", "", 12.0),
            ):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNone(result.symbols)
        self.assertTrue(any("invalid or truncated JSON" in item for item in result.diagnostics))

    def test_contract_shape_mismatch_is_reported(self) -> None:
        bad_payload = json.dumps({
            "schemaVersion": 1,
            "nodes": [],
            "links": [],
            "symbols": [],
            "meta": {
                "sdkVersion": "10.0.100",
                "helperVersion": "0.2.0",
                "helperProtocolVersion": "1",
                "diagnostics": [],
                "timing": {"elapsedMs": 8},
            },
        })
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(Path("/tmp/helper.dll"), []),
            ), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._run_command",
                return_value=CommandResult(0, bad_payload, "", 12.0),
            ):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNone(result.symbols)
        self.assertTrue(any("did not match the helper contract" in item for item in result.diagnostics))

    def test_timeout_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(Path("/tmp/helper.dll"), []),
            ), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._run_command",
                side_effect=TimeoutError("Command timed out after 10.0s"),
            ):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNone(result.symbols)
        self.assertTrue(any("timed out" in item for item in result.diagnostics))

    def test_successful_smoke_output_returns_symbols_and_meta_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Service.cs"
            path.write_text("public class Service {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(Path("/tmp/helper.dll"), []),
            ), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._run_command",
                return_value=CommandResult(0, _valid_payload(), "", 12.0),
            ):
                result = extract_csharp_symbols_with_helper(path)

        self.assertIsNotNone(result.symbols)
        assert result.symbols is not None
        self.assertEqual(result.symbols[0]["name"], "WidgetService")
        self.assertEqual(result.nodes[0]["id"], "src/WidgetService.cs")
        self.assertEqual(result.external_nodes[0]["id"], "nuget:Newtonsoft.Json/13.0.3")
        self.assertEqual(result.links[0]["sourceSpan"]["startLine"], 4)
        self.assertEqual(result.symbols[0]["accessibility"], "public")
        self.assertEqual(result.meta["helperProtocolVersion"], "1")
        self.assertIn("helper smoke ok", result.diagnostics)

    def test_repo_analysis_adapts_helper_payload_to_analyzer_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "WidgetService.cs").write_text("public class WidgetService {}")
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.inspect_dotnet_runtime", return_value={
                "supported": True,
                "dotnetPath": "/tmp/dotnet",
                "dotnetSdkVersion": "10.0.100",
                "diagnostics": [],
            }), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._ensure_helper_built",
                return_value=(Path("/tmp/helper.dll"), []),
            ), patch(
                "codeindex.analyzers.csharp_analyzer_roslyn._run_command",
                return_value=CommandResult(0, _valid_payload(), "", 12.0),
            ):
                nodes, external_nodes, links_map, meta = analyze(root, {})

        self.assertEqual(nodes[0]["group"], 0)
        self.assertEqual(external_nodes[0]["id"], "nuget:Newtonsoft.Json/13.0.3")
        self.assertEqual(links_map, {})
        self.assertEqual(meta["actualModes"]["csharp"], "roslyn")
        self.assertEqual(meta["analysisModes"]["csharp"]["roslyn"], 1)
        self.assertEqual(meta["linkRecords"][0]["target"], "nuget:Newtonsoft.Json/13.0.3")
        self.assertEqual(meta["linkRecords"][0]["sourceSpan"]["endColumn"], 20)


if __name__ == "__main__":
    unittest.main()
#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeindex.index import build
from codeindex.symbols import build_symbol_index


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "razor_blazor_spike"
HELPER_PROJECT = Path(__file__).resolve().parent.parent / "codeindex" / "roslyn_helper" / "CodeIndex.RoslynHelper.csproj"


def _copy_fixture(root: Path) -> None:
    shutil.copytree(FIXTURE_ROOT, root, dirs_exist_ok=True)


def _runtime() -> dict:
    return {
        "dotnetPath": "/tmp/dotnet",
        "dotnetSdkVersion": "10.0.100",
        "supported": True,
        "diagnostics": [],
    }


def _fake_csharp_analyze(root: Path, group_map: dict) -> tuple[list[dict], list[dict], dict, dict]:
    group = group_map.setdefault("app", 0)
    return (
        [
            {
                "id": "Pages/Dashboard.razor.cs",
                "type": "module",
                "language": "csharp",
                "loc": 8,
                "imports": 1,
                "group": group,
            },
            {
                "id": "Shared/IWidget.cs",
                "type": "module",
                "language": "csharp",
                "loc": 14,
                "imports": 0,
                "group": group,
            },
        ],
        [],
        {},
        {
            "total_files": 2,
            "total_loc": 22,
            "actualModes": {"csharp": "roslyn"},
            "linkRecords": [
                {
                    "source": "Pages/Dashboard.razor.cs",
                    "target": "Shared/IWidget.cs",
                    "weight": 1,
                    "symbol": "IWidget",
                    "sourceSpan": {
                        "startLine": 3,
                        "startColumn": 7,
                        "endLine": 3,
                        "endColumn": 30,
                    },
                }
            ],
            "diagnostics": [],
        },
    )


def _fake_csharp_symbols(path: Path) -> list[dict] | None:
    if path.name == "Dashboard.razor.cs":
        return [
            {
                "name": "Dashboard",
                "line": 5,
                "kind": "class",
                "exported": True,
                "signature": "RazorBlazorSpike.Pages.Dashboard<TItem>",
                "sourceSpan": {
                    "startLine": 5,
                    "startColumn": 1,
                    "endLine": 8,
                    "endColumn": 2,
                },
            }
        ]
    if path.name == "IWidget.cs":
        return [
            {
                "name": "IWidget",
                "line": 3,
                "kind": "interface",
                "exported": True,
                "signature": "RazorBlazorSpike.Shared.IWidget",
            },
            {
                "name": "WidgetStatus",
                "line": 11,
                "kind": "enum",
                "exported": True,
                "signature": "RazorBlazorSpike.Shared.WidgetStatus",
            },
        ]
    return []


class RazorBlazorSpikeTests(unittest.TestCase):
    def test_deferred_scope_does_not_use_disallowed_razor_apis(self) -> None:
        project = HELPER_PROJECT.read_text()

        self.assertNotIn("Microsoft.CodeAnalysis.Razor", project)
        self.assertNotIn("Microsoft.VisualStudio", project)

    def test_fixture_keeps_broad_razor_and_blazor_syntax_under_truth_data(self) -> None:
        truth = json.loads((FIXTURE_ROOT / "truth.json").read_text())
        combined = "\n".join(path.read_text() for path in FIXTURE_ROOT.rglob("*.razor"))

        self.assertEqual(truth["supportLevel"], "deferred")
        self.assertFalse(truth["precisionGateApplies"])
        for required in (
            "@page",
            "@rendermode",
            "@using",
            "@typeparam",
            "@implements",
            "@inject",
            "@attribute",
            "@layout",
            "<CascadingValue",
            "<EditForm",
            "<InputText",
            "<Virtualize",
            "<WidgetCard",
            "@key",
            "@ref",
            "@foreach",
            "@switch",
            "[CascadingParameter]",
            "RenderFragment",
            "EventCallback",
        ):
            self.assertIn(required, combined)

        self.assertIn("mapped Razor source spans", truth["unsupportedScopes"])
        self.assertIn("code-behind partials as Razor components", truth["unsupportedScopes"])

    def test_dependency_index_reports_razor_deferred_without_razor_nodes_or_spans(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _copy_fixture(root)
            with patch("codeindex.analyzers.csharp_analyzer_roslyn.analyze", side_effect=_fake_csharp_analyze), patch(
                "codeindex.runtime_contract.inspect_dotnet_runtime",
                return_value=_runtime(),
            ):
                data = build(str(root), root / "codeindex-test.json", first_use_budget_seconds=4.0)

        meta = data["meta"]
        self.assertIn("razor", meta["languages"])
        self.assertEqual(meta["requestedModes"]["razor"], "roslyn")
        self.assertEqual(meta["actualModes"]["razor"], "deferred")
        self.assertEqual(meta["analysisRuntime"]["razor"]["actualMode"], "deferred")
        self.assertEqual(meta["analysisRuntime"]["razor"]["analyzer"], "none")
        self.assertEqual(meta["analysisRuntime"]["razor"]["provenance"], "phase-4-razor-deferred")
        self.assertTrue(any("Razor/Blazor Roslyn support is deferred" in item for item in meta["diagnostics"]))

        self.assertFalse(any(node["id"].endswith(".razor") for node in data["nodes"]))
        self.assertFalse(
            any(
                link.get("source", "").endswith(".razor") or link.get("target", "").endswith(".razor")
                for link in data["links"]
            )
        )
        self.assertFalse(any(link.get("source", "").endswith(".razor") and "sourceSpan" in link for link in data["links"]))

        csharp_span = next(link["sourceSpan"] for link in data["links"] if link.get("symbol") == "IWidget")
        self.assertEqual(csharp_span["startLine"], 3)
        self.assertEqual(csharp_span["startColumn"], 7)

    def test_symbol_index_reports_razor_deferred_without_razor_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _copy_fixture(root)
            with patch("codeindex.symbol_extractor._extract_csharp_roslyn", side_effect=_fake_csharp_symbols), patch(
                "codeindex.runtime_contract.inspect_dotnet_runtime",
                return_value=_runtime(),
            ):
                data = build_symbol_index(str(root), first_use_budget_seconds=4.0)
            self.assertFalse((root / "symbolindex.json").exists())

        meta = data["meta"]
        self.assertEqual(meta["requestedModes"]["razor"], "roslyn")
        self.assertEqual(meta["actualModes"]["razor"], "deferred")
        self.assertEqual(meta["analysisRuntime"]["razor"]["actualMode"], "deferred")
        self.assertEqual(meta["analysisRuntime"]["razor"]["analyzer"], "none")
        self.assertTrue(any("mapped Razor source spans" in item for item in meta["diagnostics"]))

        self.assertNotIn("Pages/Dashboard.razor", data["file_symbols"])
        self.assertNotIn("Components/WidgetCard.razor", data["file_symbols"])
        self.assertFalse(any(path.endswith(".razor") for path in data["file_symbols"]))

        dashboard = data["file_symbols"]["Pages/Dashboard.razor.cs"][0]
        self.assertEqual(dashboard["analysisMode"], "roslyn")
        self.assertEqual(dashboard["sourceSpan"]["startLine"], 5)


if __name__ == "__main__":
    unittest.main()
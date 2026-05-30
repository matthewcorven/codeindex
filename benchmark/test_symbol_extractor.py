#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeindex.symbol_extractor import extract_csharp, extract_symbols


class CSharpSymbolExtractorTests(unittest.TestCase):
    def assert_metadata(self, symbol: dict, mode: str, extractor: str) -> None:
        self.assertEqual(symbol["analysisMode"], mode)
        self.assertEqual(symbol["extractor"], extractor)
        self.assertIn("extractorVersion", symbol)
        self.assertIn("confidence", symbol)
        self.assertIn("schemaVersion", symbol)

    def test_csharp_regex_fallback_extracts_types_and_methods(self) -> None:
        src = """
public class PublicService
{
    public int Run(string input) => 1;
    private void Hidden() { }
}

internal class InternalOnly {}
"""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "service.cs"
            path.write_text(src)
            symbols = extract_symbols(path)

        by_name = {s["name"]: s for s in symbols}
        self.assertEqual(by_name["PublicService"]["kind"], "class")
        self.assertTrue(by_name["PublicService"]["exported"])
        self.assertEqual(by_name["Run"]["kind"], "function")
        self.assertTrue(by_name["Run"]["exported"])
        self.assertFalse(by_name["InternalOnly"]["exported"])
        self.assert_metadata(by_name["PublicService"], "regex", "csharp-regex")

    def test_csharp_prefers_roslyn_output_when_available(self) -> None:
        roslyn = [{"name": "FromRoslyn", "line": 7, "kind": "class", "exported": True}]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "service.cs"
            path.write_text("public class A {}")
            with patch("codeindex.symbol_extractor._extract_csharp_roslyn", return_value=roslyn):
                symbols = extract_csharp(path)
        self.assertEqual(symbols[0]["name"], "FromRoslyn")
        self.assert_metadata(symbols[0], "roslyn", "codeindex-csharp-symbols")
        self.assertGreater(symbols[0]["confidence"], 0.9)

    def test_python_ast_symbols_include_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "service.py"
            path.write_text("class Service:\n    def run(self):\n        pass\n")
            symbols = extract_symbols(path)
        by_name = {s["name"]: s for s in symbols}
        self.assert_metadata(by_name["Service"], "ast", "python-ast")
        self.assertGreater(by_name["Service"]["confidence"], 0.9)

    def test_javascript_regex_symbols_include_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "component.ts"
            path.write_text("export class Widget {}\nexport function render() {}\n")
            symbols = extract_symbols(path)
        by_name = {s["name"]: s for s in symbols}
        self.assert_metadata(by_name["Widget"], "regex", "javascript-regex")
        self.assertLess(by_name["Widget"]["confidence"], 0.9)


if __name__ == "__main__":
    unittest.main()

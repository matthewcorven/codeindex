#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeindex.symbol_extractor import extract_csharp, extract_symbols


class CSharpSymbolExtractorTests(unittest.TestCase):
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

    def test_csharp_prefers_roslyn_output_when_available(self) -> None:
        roslyn = [{"name": "FromRoslyn", "line": 7, "kind": "class", "exported": True}]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "service.cs"
            path.write_text("public class A {}")
            with patch("codeindex.symbol_extractor._extract_csharp_roslyn", return_value=roslyn):
                symbols = extract_csharp(path)
        self.assertEqual(symbols, roslyn)


if __name__ == "__main__":
    unittest.main()

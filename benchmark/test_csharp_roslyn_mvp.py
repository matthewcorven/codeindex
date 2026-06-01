#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codeindex.runtime_contract import inspect_dotnet_runtime


REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)


def _require_supported_runtime(test_case: unittest.TestCase) -> None:
    runtime = inspect_dotnet_runtime()
    if not runtime.get("supported") or not runtime.get("dotnetPath"):
        test_case.skipTest("A supported .NET 10 SDK is required for Roslyn MVP fixture validation.")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _create_project_fixture(root: Path) -> None:
    _write(
        root / "Lib" / "Lib.csproj",
        "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
        "  <PropertyGroup>\n"
        "    <TargetFramework>net10.0</TargetFramework>\n"
        "    <ImplicitUsings>enable</ImplicitUsings>\n"
        "    <Nullable>enable</Nullable>\n"
        "  </PropertyGroup>\n"
        "</Project>\n",
    )
    _write(
        root / "App" / "App.csproj",
        "<Project Sdk=\"Microsoft.NET.Sdk\">\n"
        "  <PropertyGroup>\n"
        "    <OutputType>Exe</OutputType>\n"
        "    <TargetFramework>net10.0</TargetFramework>\n"
        "    <ImplicitUsings>enable</ImplicitUsings>\n"
        "    <Nullable>enable</Nullable>\n"
        "  </PropertyGroup>\n"
        "  <ItemGroup>\n"
        "    <ProjectReference Include=\"../Lib/Lib.csproj\" />\n"
        "    <PackageReference Include=\"Newtonsoft.Json\" Version=\"13.0.3\" />\n"
        "  </ItemGroup>\n"
        "</Project>\n",
    )
    _write(
        root / "Lib" / "Widget.Part1.cs",
        "namespace Fixture.Lib;\n\n"
        "public partial class Widget<T>\n"
        "{\n"
        "    public static Widget<T> Create(T value) => new(value);\n"
        "}\n",
    )
    _write(
        root / "Lib" / "Widget.Part2.cs",
        "namespace Fixture.Lib;\n\n"
        "public partial class Widget<T>\n"
        "{\n"
        "    public Widget(T value)\n"
        "    {\n"
        "        Value = value;\n"
        "    }\n\n"
        "    public T Value { get; }\n"
        "}\n",
    )
    _write(
        root / "Lib" / "WidgetExtensions.cs",
        "namespace Fixture.Lib;\n\n"
        "public static class WidgetExtensions\n"
        "{\n"
        "    public static string Describe<T>(this Widget<T> widget) => widget.Value?.ToString() ?? string.Empty;\n"
        "}\n",
    )
    _write(
        root / "App" / "Program.cs",
        "using Fixture.Lib;\n"
        "using JsonConvertAlias = Newtonsoft.Json.JsonConvert;\n"
        "using WidgetAlias = Fixture.Lib.Widget<string>;\n\n"
        "var widget = WidgetAlias.Create(\"phase3\");\n"
        "var summary = widget.Describe();\n"
        "var payload = JsonConvertAlias.SerializeObject(new List<WidgetAlias> { widget });\n"
        "Console.WriteLine(summary + payload.Length);\n",
    )

    solution = _run(["dotnet", "new", "sln", "--name", "Fixture"], cwd=root)
    if solution.returncode != 0:
        raise AssertionError(solution.stderr or solution.stdout or "dotnet new sln failed")
    add = _run(["dotnet", "sln", "add", "App/App.csproj", "Lib/Lib.csproj"], cwd=root)
    if add.returncode != 0:
        raise AssertionError(add.stderr or add.stdout or "dotnet sln add failed")
    restore = _run(["dotnet", "restore", "App/App.csproj"], cwd=root)
    if restore.returncode != 0:
        raise unittest.SkipTest(restore.stderr or restore.stdout or "dotnet restore failed")


def _create_loose_file_fixture(root: Path) -> None:
    _write(
        root / "LooseWidget.cs",
        "namespace Fixture.Loose;\n\n"
        "using NameList = System.Collections.Generic.List<string>;\n\n"
        "public partial class LooseWidget\n"
        "{\n"
        "    public NameList Names { get; } = new();\n"
        "}\n",
    )


class CSharpRoslynMvpFixtureTests(unittest.TestCase):
    def test_curated_project_fixture_meets_dependency_and_symbol_truth(self) -> None:
        _require_supported_runtime(self)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _create_project_fixture(root)

            analyze = _run([sys.executable, "-m", "codeindex.cli", "analyze", str(root)], cwd=REPO_ROOT)
            self.assertEqual(analyze.returncode, 0, analyze.stderr or analyze.stdout)

            symbols = _run([sys.executable, "-m", "codeindex.cli", "symbols", str(root)], cwd=REPO_ROOT)
            self.assertEqual(symbols.returncode, 0, symbols.stderr or symbols.stdout)

            index = json.loads((root / "codeindex.json").read_text())
            symbol_index = json.loads((root / "symbolindex.json").read_text())

        self.assertEqual(index["meta"]["actualModes"]["csharp"], "roslyn")
        self.assertEqual(symbol_index["meta"]["actualModes"]["csharp"], "roslyn")
        self.assertIn("helperVersion", index["meta"]["analysisRuntime"]["csharp"])
        self.assertIn("helperElapsedMs", index["meta"]["analysisRuntime"]["csharp"]["timings"])
        self.assertIn("helperVersion", symbol_index["meta"]["analysisRuntime"]["csharp"])
        self.assertIn("helperElapsedMs", symbol_index["meta"]["analysisRuntime"]["csharp"]["timings"])

        app_links = [link for link in index["links"] if link["source"] == "App/Program.cs"]
        actual_targets = {link["target"] for link in app_links}
        expected_targets = {
            "Lib/Widget.Part1.cs",
            "Lib/Widget.Part2.cs",
            "Lib/WidgetExtensions.cs",
            "nuget:Newtonsoft.Json/13.0.3",
        }
        precision = len(actual_targets & expected_targets) / len(actual_targets)
        recall = len(actual_targets & expected_targets) / len(expected_targets)
        self.assertGreaterEqual(precision, 0.95)
        self.assertGreaterEqual(recall, 0.92)

        package_link = next(link for link in app_links if link["target"] == "nuget:Newtonsoft.Json/13.0.3")
        self.assertEqual(package_link["symbol"], "JsonConvert")
        self.assertEqual(package_link["sourceSpan"]["startLine"], 2)
        self.assertEqual(package_link["sourceSpan"]["startColumn"], 26)

        file_symbols = symbol_index["file_symbols"]
        part1 = {symbol["name"]: symbol for symbol in file_symbols["Lib/Widget.Part1.cs"]}
        part2 = {symbol["name"]: symbol for symbol in file_symbols["Lib/Widget.Part2.cs"]}
        extensions = {symbol["name"]: symbol for symbol in file_symbols["Lib/WidgetExtensions.cs"]}

        self.assertEqual(part1["Widget"]["analysisMode"], "roslyn")
        self.assertEqual(part1["Widget"]["signature"], "Fixture.Lib.Widget<T>")
        self.assertEqual(part1["Widget"]["sourceSpan"]["startLine"], 3)
        self.assertEqual(part1["Create"]["containingType"], "Widget")
        self.assertEqual(part2["Widget"]["sourceSpan"]["endLine"], 11)
        self.assertEqual(part2["Value"]["kind"], "property")
        self.assertEqual(extensions["Describe"]["containingType"], "WidgetExtensions")
        self.assertIn("Widget<T>", extensions["Describe"]["signature"])

    def test_loose_file_repo_uses_roslyn_with_truthful_diagnostics(self) -> None:
        _require_supported_runtime(self)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _create_loose_file_fixture(root)

            analyze = _run([sys.executable, "-m", "codeindex.cli", "analyze", str(root)], cwd=REPO_ROOT)
            self.assertEqual(analyze.returncode, 0, analyze.stderr or analyze.stdout)

            symbols = _run([sys.executable, "-m", "codeindex.cli", "symbols", str(root)], cwd=REPO_ROOT)
            self.assertEqual(symbols.returncode, 0, symbols.stderr or symbols.stdout)

            index = json.loads((root / "codeindex.json").read_text())
            symbol_index = json.loads((root / "symbolindex.json").read_text())

        self.assertEqual(index["meta"]["actualModes"]["csharp"], "roslyn")
        self.assertTrue(any("AdhocWorkspace" in item for item in index["meta"]["diagnostics"]))
        self.assertEqual(symbol_index["meta"]["actualModes"]["csharp"], "roslyn")
        loose_symbols = {symbol["name"]: symbol for symbol in symbol_index["file_symbols"]["LooseWidget.cs"]}
        self.assertEqual(loose_symbols["LooseWidget"]["analysisMode"], "roslyn")
        self.assertEqual(loose_symbols["Names"]["kind"], "property")
        self.assertEqual(loose_symbols["Names"]["accessibility"], "public")


if __name__ == "__main__":
    unittest.main()
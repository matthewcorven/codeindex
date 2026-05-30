#!/usr/bin/env python3
"""Integration fixture for C# / Razor / Blazor analyzer support."""
from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codeindex.analyze import analyze
from codeindex.symbols import build_symbol_index


PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


class Results:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def check(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"  {PASS} {label}")
        else:
            self.failed += 1
            print(f"  {FAIL} {label}" + (f"\n      {detail}" if detail else ""))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n")


def build_fixture(root: Path) -> None:
    write(root / "Sample.csproj", """
<Project Sdk="Microsoft.NET.Sdk.BlazorWebAssembly">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Components.WebAssembly" Version="8.0.0" />
  </ItemGroup>
</Project>
""")
    write(root / "Program.cs", """
using MyApp.Services;

namespace MyApp;

public class Program
{
    public static void Main(string[] args)
    {
        _ = typeof(WeatherService);
    }
}
""")
    write(root / "Services" / "WeatherService.cs", """
namespace MyApp.Services;

public class WeatherService
{
    public Task<string> ForecastAsync() => Task.FromResult("sunny");
}
""")
    write(root / "Components" / "Counter.razor", """
@namespace MyApp.Components
@using MyApp.Services
@inject WeatherService WeatherService

<HelperWidget />

@code {
    private int currentCount;
    public void IncrementCount() => currentCount++;
}
""")
    write(root / "Components" / "Counter.razor.cs", """
namespace MyApp.Components;

public partial class Counter
{
    protected string Title => "Counter";
}
""")
    write(root / "Components" / "HelperWidget.razor", """
@namespace MyApp.Components
<p>Helper</p>
""")


def main() -> None:
    results = Results()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        build_fixture(root)
        data = analyze(str(root))
        nodes = {n["id"]: n for n in data["nodes"]}
        links = {(l["source"], l["target"]) for l in data["links"]}

        results.check("detects csharp", "csharp" in data["meta"].get("languages", []))
        results.check("detects blazor framework", data["meta"].get("framework") == "blazor")
        results.check("marks C# analysis as heuristic", data["meta"].get("analysisModes", {}).get("csharp") == "heuristic")
        results.check("marks Razor analysis as heuristic", data["meta"].get("analysisModes", {}).get("razor") == "heuristic")
        results.check("indexes Program.cs", "Program.cs" in nodes)
        results.check("indexes Razor component", "Components/Counter.razor" in nodes)
        results.check("classifies Razor as component", nodes["Components/Counter.razor"].get("type") == "component")
        results.check(
            "links C# using to internal namespace",
            ("Program.cs", "Services/WeatherService.cs") in links,
            str(sorted(links)),
        )
        results.check(
            "links Razor component tag",
            ("Components/Counter.razor", "Components/HelperWidget.razor") in links,
            str(sorted(links)),
        )
        results.check(
            "links Razor code-behind",
            ("Components/Counter.razor", "Components/Counter.razor.cs") in links,
            str(sorted(links)),
        )

        symbol_data = build_symbol_index(str(root))
        symbols = symbol_data.get("symbols", {})
        results.check("extracts C# class symbol", "WeatherService" in symbols)
        results.check("extracts Razor component symbol", "Counter" in symbols)
        results.check("extracts Razor code method symbol", "IncrementCount" in symbols)

    total = results.passed + results.failed
    print(f"\n{results.passed}/{total} passed")
    raise SystemExit(0 if results.failed == 0 else 1)


if __name__ == "__main__":
    main()
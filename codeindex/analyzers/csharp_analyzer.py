"""C# / Razor / Blazor repository analyzer.

This analyzer is intentionally dependency-free. It provides a useful baseline for
dependency graphs in .NET repositories while the Roslyn-backed semantic path is
assessed separately.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .base import load_gitignore_patterns, is_ignored, is_skip_dir, dir_group

CSHARP_EXTENSIONS = {".cs", ".csx", ".razor", ".cshtml"}
PROJECT_EXTENSIONS = {".csproj"}

_SKIP_PARTS = {"bin", "obj", "generated", "generated-sources"}

_NAMESPACE_RE = re.compile(
    r"^\s*namespace\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*(?:[;{])",
    re.MULTILINE,
)
_RAZOR_NAMESPACE_RE = re.compile(
    r"^\s*@namespace\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)",
    re.MULTILINE,
)
_TYPE_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]\s*)*"
    r"(?:(?:public|internal|private|protected|abstract|sealed|static|partial|file|readonly|unsafe)\s+)*"
    r"(class|interface|struct|enum|record(?:\s+(?:class|struct))?)\s+([A-Za-z_]\w*)",
    re.MULTILINE,
)
_USING_RE = re.compile(
    r"^\s*using\s+(?:static\s+)?(?:[A-Za-z_]\w*\s*=\s*)?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*;",
    re.MULTILINE,
)
_RAZOR_USING_RE = re.compile(
    r"^\s*@using\s+(?:static\s+)?([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)",
    re.MULTILINE,
)
_RAZOR_INJECT_RE = re.compile(
    r"^\s*@inject\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\b",
    re.MULTILINE,
)
_COMPONENT_TAG_RE = re.compile(r"<([A-Z][A-Za-z0-9_.]*)\b")


def _is_generated(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return bool(parts & _SKIP_PARTS) or path.name.endswith((".g.cs", ".designer.cs"))


def collect_files(root: Path, patterns: list) -> list[Path]:
    files = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in CSHARP_EXTENSIONS | PROJECT_EXTENSIONS:
            continue
        if is_skip_dir(p) or is_ignored(p, root, patterns) or _is_generated(p):
            continue
        files.append(p)
    return sorted(files)


def detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".razor", ".cshtml"}:
        return "razor"
    return "csharp"


def node_type(path: Path) -> str:
    suffix = path.suffix.lower()
    stem_lower = path.stem.lower()
    parts_lower = [p.lower() for p in path.parts]

    if suffix == ".csproj" or stem_lower in {"program", "startup"}:
        return "config"
    if suffix == ".razor":
        return "route" if "pages" in parts_lower else "component"
    if suffix == ".cshtml":
        return "route"
    if "controllers" in parts_lower or stem_lower.endswith("controller"):
        return "route"
    if any(p in {"services", "repositories", "data"} for p in parts_lower):
        return "store"
    if stem_lower.endswith(("service", "repository", "context", "store")):
        return "store"
    if "test" in parts_lower or stem_lower.endswith(("test", "tests", "spec")):
        return "module"
    return "module"


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _namespace(source: str, path: Path) -> str:
    if path.suffix.lower() in {".razor", ".cshtml"}:
        match = _RAZOR_NAMESPACE_RE.search(source)
        return match.group(1) if match else ""
    match = _NAMESPACE_RE.search(source)
    return match.group(1) if match else ""


def _type_names(source: str, path: Path) -> list[str]:
    if path.suffix.lower() == ".razor":
        return [path.stem]
    return [m.group(2) for m in _TYPE_RE.finditer(source)]


def _code_imports(source: str) -> list[str]:
    return [m.group(1) for m in _USING_RE.finditer(source)]


def _razor_imports(source: str) -> list[str]:
    imports = [m.group(1) for m in _RAZOR_USING_RE.finditer(source)]
    imports.extend(m.group(1) for m in _RAZOR_INJECT_RE.finditer(source))
    return imports


def _component_tags(source: str) -> list[str]:
    tags = []
    seen = set()
    for match in _COMPONENT_TAG_RE.finditer(source):
        name = match.group(1).split(".")[-1]
        if name not in seen:
            seen.add(name)
            tags.append(name)
    return tags


def _package_name(namespace_or_type: str) -> str:
    parts = namespace_or_type.split(".")
    if len(parts) >= 2 and parts[0] in {"Microsoft", "System"}:
        return ".".join(parts[:2])
    return parts[0]


def _xml_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _project_refs(path: Path, root: Path, all_rel: set[str]) -> tuple[list[str], list[str]]:
    try:
        project = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return [], []

    internal = []
    packages = []
    for elem in project.iter():
        local = _xml_local(elem.tag)
        include = elem.attrib.get("Include") or elem.attrib.get("Update")
        if not include:
            continue
        if local == "ProjectReference":
            try:
                rel = str((path.parent / include).resolve().relative_to(root))
            except ValueError:
                continue
            if rel in all_rel:
                internal.append(rel)
        elif local == "PackageReference":
            packages.append(include)
    return internal, packages


def analyze(root: Path, group_map: dict):
    patterns = load_gitignore_patterns(root)
    files = collect_files(root, patterns)

    if not files:
        return [], [], {}, {"total_files": 0, "total_loc": 0}

    all_rel = {str(f.relative_to(root)) for f in files}
    sources = {f: _read(f) for f in files}
    code_files = [f for f in files if f.suffix.lower() in CSHARP_EXTENSIONS]
    project_files = [f for f in files if f.suffix.lower() in PROJECT_EXTENSIONS]

    namespace_files: dict[str, set[str]] = {}
    type_files: dict[str, set[str]] = {}
    component_files: dict[str, str] = {}

    for f in code_files:
        rel = str(f.relative_to(root))
        source = sources[f]
        ns = _namespace(source, f)
        if ns:
            namespace_files.setdefault(ns, set()).add(rel)
        for name in _type_names(source, f):
            type_files.setdefault(name, set()).add(rel)
            if ns:
                type_files.setdefault(f"{ns}.{name}", set()).add(rel)
        if f.suffix.lower() == ".razor":
            component_files[f.stem] = rel

    nodes = []
    links_map = {}
    external_nodes = {}
    total_loc = 0

    def add_link(source: str, target: str) -> None:
        if source == target:
            return
        key = (source, target)
        links_map[key] = links_map.get(key, 0) + 1

    def add_external(source: str, name: str) -> None:
        pkg = _package_name(name)
        if pkg not in external_nodes:
            external_nodes[pkg] = {
                "id": pkg,
                "type": "import",
                "language": "csharp",
                "size": 40,
                "loc": 0,
                "group": 9000,
                "imports": 0,
            }
        add_link(source, pkg)

    def resolve_reference(source_rel: str, reference: str) -> None:
        targets = type_files.get(reference) or namespace_files.get(reference)
        if not targets and "." in reference:
            targets = type_files.get(reference.split(".")[-1])
        if targets:
            for target in sorted(targets):
                add_link(source_rel, target)
        else:
            add_external(source_rel, reference)

    for f in files:
        rel = str(f.relative_to(root))
        source = sources[f]
        loc = source.count("\n") + 1 if source else 0
        total_loc += loc

        suffix = f.suffix.lower()
        imports = []
        if suffix in CSHARP_EXTENSIONS:
            imports = _razor_imports(source) if suffix in {".razor", ".cshtml"} else _code_imports(source)
        elif suffix in PROJECT_EXTENSIONS:
            project_links, packages = _project_refs(f, root, all_rel)
            imports = project_links + packages

        nodes.append({
            "id": rel,
            "type": node_type(f),
            "language": detect_language(f),
            "framework": "blazor" if any(p.suffix.lower() == ".razor" for p in code_files) else "dotnet",
            "size": loc,
            "loc": loc,
            "group": dir_group(f, root, group_map),
            "imports": len(imports),
        })

        if suffix in CSHARP_EXTENSIONS:
            for imp in imports:
                resolve_reference(rel, imp)
            if suffix in {".razor", ".cshtml"}:
                for tag in _component_tags(source):
                    target = component_files.get(tag)
                    if target:
                        add_link(rel, target)
                code_behind = f.with_suffix(f.suffix + ".cs")
                try:
                    code_behind_rel = str(code_behind.relative_to(root))
                except ValueError:
                    code_behind_rel = ""
                if code_behind_rel in all_rel:
                    add_link(rel, code_behind_rel)
        elif suffix in PROJECT_EXTENSIONS:
            project_links, packages = _project_refs(f, root, all_rel)
            for target in project_links:
                add_link(rel, target)
            for package in packages:
                add_external(rel, package)

    meta = {
        "total_files": len(files),
        "total_loc": total_loc,
        "framework": "dotnet",
        "analysisModes": {"csharp": "heuristic", "razor": "heuristic"},
    }
    if any(f.suffix.lower() == ".razor" for f in code_files):
        meta["framework"] = "blazor"
    if project_files:
        meta["packageManager"] = "nuget"

    return nodes, list(external_nodes.values()), links_map, meta
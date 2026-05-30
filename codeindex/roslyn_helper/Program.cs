using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.Build.Locator;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.MSBuild;
using Microsoft.CodeAnalysis.Text;

const string SupportedProtocolVersion = "1";
const int SchemaVersion = 1;

var started = Stopwatch.StartNew();
var parsedArgs = ParseArgs(args);

var requestedProtocol = parsedArgs.GetValueOrDefault("protocol-version") ?? SupportedProtocolVersion;
if (!string.Equals(requestedProtocol, SupportedProtocolVersion, StringComparison.Ordinal))
{
    Console.Error.WriteLine(
        $"Unsupported helper protocol version '{requestedProtocol}'. Expected '{SupportedProtocolVersion}'.");
    return 2;
}

var repoPath = parsedArgs.GetValueOrDefault("repo");
var filePath = parsedArgs.GetValueOrDefault("file");
if (string.IsNullOrWhiteSpace(repoPath) == string.IsNullOrWhiteSpace(filePath))
{
    Console.Error.WriteLine("Specify exactly one of --repo or --file.");
    return 2;
}

var targetPath = repoPath ?? filePath!;
if ((repoPath is not null && !Directory.Exists(targetPath)) || (filePath is not null && !File.Exists(targetPath)))
{
    Console.Error.WriteLine(repoPath is not null ? $"C# repo not found: {targetPath}" : $"C# file not found: {targetPath}");
    return 2;
}

var helperVersion =
    typeof(Program).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
    ?? typeof(Program).Assembly.GetName().Version?.ToString()
    ?? "0.3.0";

HelperAnalysis analysis;
try
{
    analysis = await AnalyzeAsync(targetPath, repoPath is not null);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Roslyn helper failed: {ex.Message}");
    return 2;
}

var payload = new HelperPayload(
    SchemaVersion,
    analysis.Nodes,
    analysis.ExternalNodes,
    analysis.Links,
    analysis.Symbols,
    new HelperMeta(
        parsedArgs.GetValueOrDefault("sdk-version") ?? "unknown-sdk",
        helperVersion,
        SupportedProtocolVersion,
        analysis.Diagnostics,
        new HelperTiming(started.ElapsedMilliseconds)));

var options = new JsonSerializerOptions
{
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};
Console.Out.Write(JsonSerializer.Serialize(payload, options));
return 0;

Dictionary<string, string> ParseArgs(string[] args)
{
    var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    for (var index = 0; index < args.Length; index++)
    {
        var current = args[index];
        if (!current.StartsWith("--", StringComparison.Ordinal))
        {
            continue;
        }

        var key = current[2..];
        if (index + 1 >= args.Length || args[index + 1].StartsWith("--", StringComparison.Ordinal))
        {
            values[key] = string.Empty;
            continue;
        }

        values[key] = args[index + 1];
        index++;
    }

    return values;
}

async Task<HelperAnalysis> AnalyzeAsync(string targetPath, bool repoMode)
{
    var diagnostics = new List<string>();
    var fullTargetPath = Path.GetFullPath(targetPath);
    var repoRoot = repoMode ? fullTargetPath : FindAnalysisRootForFile(fullTargetPath);
    var requestedFile = repoMode ? null : fullTargetPath;

    var solutionPaths = EnumerateFiles(repoRoot, "*.sln")
        .Concat(EnumerateFiles(repoRoot, "*.slnx"))
        .OrderBy(path => path.Length)
        .ThenBy(path => path, StringComparer.OrdinalIgnoreCase)
        .ToList();
    if (solutionPaths.Count > 0)
    {
        EnsureMsBuildRegistered();
        foreach (var solutionPath in solutionPaths)
        {
            using var workspace = MSBuildWorkspace.Create();
            workspace.WorkspaceFailed += (_, eventArgs) =>
            {
                if (!string.IsNullOrWhiteSpace(eventArgs.Diagnostic.Message))
                {
                    diagnostics.Add(eventArgs.Diagnostic.Message);
                }
            };
            try
            {
                var solution = await workspace.OpenSolutionAsync(solutionPath);
                return await AnalyzeProjectsAsync(
                    repoRoot,
                    solution.Projects.Where(project => IsProjectUnderRoot(project.FilePath, repoRoot)).ToList(),
                    requestedFile,
                    diagnostics);
            }
            catch (Exception ex)
            {
                diagnostics.Add($"Failed to open solution '{solutionPath}': {ex.Message}");
            }
        }
    }

    var projectPaths = EnumerateFiles(repoRoot, "*.csproj")
        .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
        .ToList();
    if (projectPaths.Count > 0)
    {
        EnsureMsBuildRegistered();
        using var workspace = MSBuildWorkspace.Create();
        workspace.WorkspaceFailed += (_, eventArgs) =>
        {
            if (!string.IsNullOrWhiteSpace(eventArgs.Diagnostic.Message))
            {
                diagnostics.Add(eventArgs.Diagnostic.Message);
            }
        };
        var projects = new List<Project>();
        foreach (var projectPath in projectPaths)
        {
            var normalizedProjectPath = Path.GetFullPath(projectPath);
            var existing = workspace.CurrentSolution.Projects.FirstOrDefault(project =>
                !string.IsNullOrWhiteSpace(project.FilePath)
                && string.Equals(Path.GetFullPath(project.FilePath), normalizedProjectPath, StringComparison.OrdinalIgnoreCase));
            if (existing is not null)
            {
                projects.Add(existing);
                continue;
            }

            projects.Add(await workspace.OpenProjectAsync(projectPath));
        }

        return await AnalyzeProjectsAsync(repoRoot, projects, requestedFile, diagnostics);
    }

    return await AnalyzeLooseFilesAsync(repoRoot, requestedFile, diagnostics);
}

async Task<HelperAnalysis> AnalyzeLooseFilesAsync(string repoRoot, string? requestedFile, List<string> diagnostics)
{
    var files = EnumerateFiles(repoRoot, "*.cs").ToList();
    if (files.Count == 0)
    {
        throw new InvalidOperationException($"No C# files were found under {repoRoot}.");
    }

    using var workspace = new AdhocWorkspace();
    var projectId = ProjectId.CreateNewId();
    var references = LoadTrustedPlatformReferences();
    var solution = workspace.CurrentSolution.AddProject(
        ProjectInfo.Create(
            projectId,
            VersionStamp.Create(),
            "LooseFiles",
            "LooseFiles",
            LanguageNames.CSharp,
            parseOptions: new CSharpParseOptions(LanguageVersion.Preview),
            compilationOptions: new CSharpCompilationOptions(OutputKind.DynamicallyLinkedLibrary),
            metadataReferences: references));

    foreach (var file in files)
    {
        var text = await File.ReadAllTextAsync(file);
        solution = solution.AddDocument(
            DocumentId.CreateNewId(projectId),
            Path.GetFileName(file),
            SourceText.From(text),
            filePath: file);
    }

    if (!workspace.TryApplyChanges(solution))
    {
        throw new InvalidOperationException("Failed to create an AdhocWorkspace for loose C# files.");
    }

    var project = workspace.CurrentSolution.GetProject(projectId)
        ?? throw new InvalidOperationException("Failed to resolve the AdhocWorkspace C# project.");
    diagnostics.Add("Analyzed loose C# files with AdhocWorkspace because no solution or project file was found.");
    return await AnalyzeProjectsAsync(repoRoot, new[] { project }, requestedFile, diagnostics);
}

async Task<HelperAnalysis> AnalyzeProjectsAsync(
    string repoRoot,
    IReadOnlyCollection<Project> projects,
    string? requestedFile,
    List<string> diagnostics)
{
    if (projects.Count == 0)
    {
        throw new InvalidOperationException($"No C# projects were found under {repoRoot}.");
    }

    var documentContexts = new List<DocumentContext>();
    var seenFiles = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    foreach (var project in projects.Where(project => string.Equals(project.Language, LanguageNames.CSharp, StringComparison.Ordinal)))
    {
        var compilation = await project.GetCompilationAsync();
        if (compilation is null)
        {
            diagnostics.Add($"Skipping project '{project.Name}' because Roslyn could not create a compilation.");
            continue;
        }

        var packageAssemblies = await LoadPackageAssemblyMapAsync(project.FilePath);
        foreach (var document in project.Documents)
        {
            if (string.IsNullOrWhiteSpace(document.FilePath) || !document.FilePath.EndsWith(".cs", StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            var absolutePath = Path.GetFullPath(document.FilePath);
            if (!IsPathUnderRoot(absolutePath, repoRoot) || !seenFiles.Add(absolutePath))
            {
                continue;
            }

            var syntaxTree = await document.GetSyntaxTreeAsync();
            var syntaxRoot = await document.GetSyntaxRootAsync();
            if (syntaxTree is null || syntaxRoot is null)
            {
                diagnostics.Add($"Skipping '{absolutePath}' because Roslyn could not load its syntax tree.");
                continue;
            }

            var semanticModel = compilation.GetSemanticModel(syntaxTree, ignoreAccessibility: true);
            var relativePath = NormalizeRelativePath(repoRoot, absolutePath);
            documentContexts.Add(new DocumentContext(
                relativePath,
                absolutePath,
                syntaxRoot,
                semanticModel,
                project,
                packageAssemblies,
                CountLoc(syntaxRoot.ToFullString())));
        }
    }

    if (documentContexts.Count == 0)
    {
        throw new InvalidOperationException($"No analyzable C# documents were found under {repoRoot}.");
    }

    var namespaceToFiles = new Dictionary<string, HashSet<string>>(StringComparer.Ordinal);
    var symbols = new List<HelperSymbol>();
    foreach (var document in documentContexts)
    {
        symbols.AddRange(ExtractSymbols(document, namespaceToFiles));
    }

    var linkMap = new Dictionary<(string Source, string Target), MutableLink>();
    foreach (var document in documentContexts)
    {
        CollectLinks(document, repoRoot, namespaceToFiles, linkMap);
    }

    var importCounts = linkMap.Values
        .GroupBy(link => link.Source, StringComparer.Ordinal)
        .ToDictionary(group => group.Key, group => group.Select(link => link.Target).Distinct(StringComparer.Ordinal).Count(), StringComparer.Ordinal);

    var nodes = documentContexts
        .Select(document => new HelperNode(
            document.RelativePath,
            "module",
            "csharp",
            document.Loc,
            document.Loc,
            importCounts.GetValueOrDefault(document.RelativePath, 0)))
        .OrderBy(node => node.Id, StringComparer.Ordinal)
        .ToList();

    var externalNodes = linkMap.Values
        .Where(link => link.Target.StartsWith("nuget:", StringComparison.Ordinal) || link.Target.StartsWith("assembly:", StringComparison.Ordinal))
        .Select(link => link.Target)
        .Distinct(StringComparer.Ordinal)
        .OrderBy(id => id, StringComparer.Ordinal)
        .Select(CreateExternalNode)
        .ToList();

    var links = linkMap.Values
        .Select(link => new HelperLink(link.Source, link.Target, link.Weight, link.SourceSpan, link.Symbol))
        .OrderBy(link => link.Source, StringComparer.Ordinal)
        .ThenBy(link => link.Target, StringComparer.Ordinal)
        .ToList();

    if (!string.IsNullOrWhiteSpace(requestedFile))
    {
        var requestedRelativePath = NormalizeRelativePath(repoRoot, requestedFile);
        var filteredLinks = links.Where(link => string.Equals(link.Source, requestedRelativePath, StringComparison.Ordinal)).ToList();
        var filteredTargets = filteredLinks.Select(link => link.Target).ToHashSet(StringComparer.Ordinal);
        nodes = nodes.Where(node => string.Equals(node.Id, requestedRelativePath, StringComparison.Ordinal)).ToList();
        externalNodes = externalNodes.Where(node => filteredTargets.Contains(node.Id)).ToList();
        links = filteredLinks;
        symbols = symbols.Where(symbol => string.Equals(symbol.File, requestedRelativePath, StringComparison.Ordinal)).ToList();
    }

    return new HelperAnalysis(nodes, externalNodes, links, symbols, diagnostics.Distinct(StringComparer.Ordinal).ToList());
}

List<PortableExecutableReference> LoadTrustedPlatformReferences()
{
    var raw = AppContext.GetData("TRUSTED_PLATFORM_ASSEMBLIES") as string;
    if (string.IsNullOrWhiteSpace(raw))
    {
        return new List<PortableExecutableReference>();
    }

    return raw.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries)
        .Select(path => MetadataReference.CreateFromFile(path))
        .OfType<PortableExecutableReference>()
        .ToList();
}

IEnumerable<HelperSymbol> ExtractSymbols(
    DocumentContext document,
    Dictionary<string, HashSet<string>> namespaceToFiles)
{
    var symbols = new List<HelperSymbol>();
    var seen = new HashSet<string>(StringComparer.Ordinal);

    foreach (var declaration in document.Root.DescendantNodes().OfType<MemberDeclarationSyntax>())
    {
        ISymbol? declaredSymbol = declaration switch
        {
            BaseTypeDeclarationSyntax typeDeclaration => document.SemanticModel.GetDeclaredSymbol(typeDeclaration),
            DelegateDeclarationSyntax delegateDeclaration => document.SemanticModel.GetDeclaredSymbol(delegateDeclaration),
            MethodDeclarationSyntax methodDeclaration => document.SemanticModel.GetDeclaredSymbol(methodDeclaration),
            PropertyDeclarationSyntax propertyDeclaration => document.SemanticModel.GetDeclaredSymbol(propertyDeclaration),
            EventDeclarationSyntax eventDeclaration => document.SemanticModel.GetDeclaredSymbol(eventDeclaration),
            _ => null,
        };
        if (declaredSymbol is null)
        {
            continue;
        }

        var kind = SymbolKindFor(declaredSymbol);
        if (kind is null)
        {
            continue;
        }

        var span = SourceSpanFrom(declaration.GetLocation());
        var key = $"{document.RelativePath}:{declaration.SpanStart}:{kind}:{declaredSymbol.Name}";
        if (!seen.Add(key))
        {
            continue;
        }

        var namespaceName = declaredSymbol.ContainingNamespace?.ToDisplayString();
        if (!string.IsNullOrWhiteSpace(namespaceName))
        {
            if (!namespaceToFiles.TryGetValue(namespaceName, out var files))
            {
                files = new HashSet<string>(StringComparer.Ordinal);
                namespaceToFiles[namespaceName] = files;
            }

            files.Add(document.RelativePath);
        }

        symbols.Add(new HelperSymbol(
            declaredSymbol.Name,
            span.StartLine,
            kind,
            declaredSymbol.DeclaredAccessibility == Accessibility.Public,
            declaredSymbol is INamedTypeSymbol typeSymbol ? ExtractTypeMethods(typeSymbol) : null,
            null,
            AccessibilityFor(declaredSymbol),
            SignatureFor(declaredSymbol),
            declaredSymbol.ContainingType?.Name,
            span,
            document.RelativePath));
    }

    return symbols;
}

void CollectLinks(
    DocumentContext document,
    string repoRoot,
    Dictionary<string, HashSet<string>> namespaceToFiles,
    Dictionary<(string Source, string Target), MutableLink> linkMap)
{
    foreach (var node in EnumerateReferenceNodes(document.Root))
    {
        var symbol = ResolveReferenceSymbol(document.SemanticModel, node);
        if (symbol is null)
        {
            continue;
        }

        foreach (var target in ResolveTargets(symbol, document, repoRoot, namespaceToFiles))
        {
            if (string.Equals(target, document.RelativePath, StringComparison.Ordinal))
            {
                continue;
            }

            var key = (document.RelativePath, target);
            if (!linkMap.TryGetValue(key, out var link))
            {
                link = new MutableLink
                {
                    Source = document.RelativePath,
                    Target = target,
                    Weight = 0,
                    SourceSpan = SourceSpanFrom(node.GetLocation()),
                    Symbol = symbol.ToDisplayString(SymbolDisplayFormat.MinimallyQualifiedFormat),
                };
                linkMap[key] = link;
            }

            link.Weight += 1;
        }
    }
}

IEnumerable<SyntaxNode> EnumerateReferenceNodes(SyntaxNode root)
{
    var seen = new HashSet<TextSpan>();

    foreach (var usingDirective in root.DescendantNodes().OfType<UsingDirectiveSyntax>())
    {
        if (usingDirective.Name is not null && seen.Add(usingDirective.Name.Span))
        {
            yield return usingDirective.Name;
        }
    }

    foreach (var baseType in root.DescendantNodes().OfType<BaseTypeSyntax>())
    {
        if (seen.Add(baseType.Type.Span))
        {
            yield return baseType.Type;
        }
    }

    foreach (var attribute in root.DescendantNodes().OfType<AttributeSyntax>())
    {
        if (seen.Add(attribute.Name.Span))
        {
            yield return attribute.Name;
        }
    }

    foreach (var simpleName in root.DescendantNodes().OfType<SimpleNameSyntax>())
    {
        if (IsDeclarationName(simpleName) || !seen.Add(simpleName.Span))
        {
            continue;
        }

        yield return simpleName;
    }
}

bool IsDeclarationName(SimpleNameSyntax nameSyntax) =>
    nameSyntax.Parent switch
    {
        BaseTypeDeclarationSyntax typeDeclaration when typeDeclaration.Identifier.Span == nameSyntax.Span => true,
        DelegateDeclarationSyntax delegateDeclaration when delegateDeclaration.Identifier.Span == nameSyntax.Span => true,
        MethodDeclarationSyntax methodDeclaration when methodDeclaration.Identifier.Span == nameSyntax.Span => true,
        PropertyDeclarationSyntax propertyDeclaration when propertyDeclaration.Identifier.Span == nameSyntax.Span => true,
        EventDeclarationSyntax eventDeclaration when eventDeclaration.Identifier.Span == nameSyntax.Span => true,
        VariableDeclaratorSyntax variableDeclarator when variableDeclarator.Identifier.Span == nameSyntax.Span => true,
        ParameterSyntax parameterSyntax when parameterSyntax.Identifier.Span == nameSyntax.Span => true,
        _ => false,
    };

ISymbol? ResolveReferenceSymbol(SemanticModel semanticModel, SyntaxNode node)
{
    if (node is NameSyntax nameSyntax)
    {
        var alias = semanticModel.GetAliasInfo(nameSyntax);
        if (alias is not null)
        {
            return alias.Target;
        }
    }

    var info = semanticModel.GetSymbolInfo(node);
    var symbol = info.Symbol ?? info.CandidateSymbols.FirstOrDefault();
    return symbol is IMethodSymbol { MethodKind: MethodKind.ReducedExtension } method ? method.ReducedFrom ?? method : symbol;
}

IEnumerable<string> ResolveTargets(
    ISymbol symbol,
    DocumentContext document,
    string repoRoot,
    Dictionary<string, HashSet<string>> namespaceToFiles)
{
    if (symbol is IAliasSymbol aliasSymbol)
    {
        return ResolveTargets(aliasSymbol.Target, document, repoRoot, namespaceToFiles);
    }

    if (symbol is INamespaceSymbol namespaceSymbol)
    {
        return namespaceToFiles.TryGetValue(namespaceSymbol.ToDisplayString(), out var files)
            ? files.OrderBy(path => path, StringComparer.Ordinal)
            : Array.Empty<string>();
    }

    var sourceTargets = symbol.Locations
        .Where(location => location.IsInSource && location.SourceTree?.FilePath is not null)
        .Select(location => NormalizeRelativePath(repoRoot, location.SourceTree!.FilePath!))
        .Distinct(StringComparer.Ordinal)
        .ToList();
    if (sourceTargets.Count > 0)
    {
        return sourceTargets;
    }

    var assemblyName = symbol.ContainingAssembly?.Name;
    if (string.IsNullOrWhiteSpace(assemblyName) || IsFrameworkAssembly(assemblyName))
    {
        return Array.Empty<string>();
    }

    if (document.PackageAssemblies.TryGetValue(assemblyName, out var packageId))
    {
        return new[] { packageId };
    }

    return new[] { $"assembly:{assemblyName}" };
}

List<string>? ExtractTypeMethods(INamedTypeSymbol symbol)
{
    var methods = symbol.GetMembers()
        .OfType<IMethodSymbol>()
        .Where(method => method.MethodKind is MethodKind.Ordinary or MethodKind.ReducedExtension)
        .Select(method => method.Name)
        .Distinct(StringComparer.Ordinal)
        .OrderBy(name => name, StringComparer.Ordinal)
        .ToList();
    return methods.Count == 0 ? null : methods;
}

string? SymbolKindFor(ISymbol symbol) => symbol switch
{
    INamedTypeSymbol namedType when namedType.TypeKind == TypeKind.Class => "class",
    INamedTypeSymbol namedType when namedType.TypeKind == TypeKind.Struct => "struct",
    INamedTypeSymbol namedType when namedType.TypeKind == TypeKind.Interface => "interface",
    INamedTypeSymbol namedType when namedType.TypeKind == TypeKind.Enum => "enum",
    INamedTypeSymbol namedType when namedType.TypeKind == TypeKind.Delegate => "delegate",
    IMethodSymbol => "function",
    IPropertySymbol => "property",
    IEventSymbol => "event",
    _ => null,
};

string AccessibilityFor(ISymbol symbol) => symbol.DeclaredAccessibility.ToString().ToLowerInvariant();

string SignatureFor(ISymbol symbol)
{
    var format = new SymbolDisplayFormat(
        globalNamespaceStyle: SymbolDisplayGlobalNamespaceStyle.Omitted,
        typeQualificationStyle: SymbolDisplayTypeQualificationStyle.NameAndContainingTypesAndNamespaces,
        propertyStyle: SymbolDisplayPropertyStyle.ShowReadWriteDescriptor,
        genericsOptions: SymbolDisplayGenericsOptions.IncludeTypeParameters,
        memberOptions: SymbolDisplayMemberOptions.IncludeParameters | SymbolDisplayMemberOptions.IncludeContainingType,
        parameterOptions: SymbolDisplayParameterOptions.IncludeType,
        miscellaneousOptions: SymbolDisplayMiscellaneousOptions.EscapeKeywordIdentifiers);
    return symbol.ToDisplayString(format);
}

HelperSourceSpan SourceSpanFrom(Location location)
{
    var lineSpan = location.GetLineSpan();
    return new HelperSourceSpan(
        lineSpan.StartLinePosition.Line + 1,
        lineSpan.StartLinePosition.Character + 1,
        lineSpan.EndLinePosition.Line + 1,
        lineSpan.EndLinePosition.Character + 1);
}

async Task<Dictionary<string, string>> LoadPackageAssemblyMapAsync(string? projectFilePath)
{
    var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
    if (string.IsNullOrWhiteSpace(projectFilePath))
    {
        return map;
    }

    var projectDirectory = Path.GetDirectoryName(projectFilePath);
    if (string.IsNullOrWhiteSpace(projectDirectory))
    {
        return map;
    }

    var assetsPath = Path.Combine(projectDirectory, "obj", "project.assets.json");
    if (!File.Exists(assetsPath))
    {
        return map;
    }

    await using var stream = File.OpenRead(assetsPath);
    using var document = await JsonDocument.ParseAsync(stream);
    if (!document.RootElement.TryGetProperty("libraries", out var librariesElement)
        || !document.RootElement.TryGetProperty("targets", out var targetsElement))
    {
        return map;
    }

    var packageKeys = librariesElement.EnumerateObject()
        .Where(property => property.Value.TryGetProperty("type", out var typeElement)
            && string.Equals(typeElement.GetString(), "package", StringComparison.OrdinalIgnoreCase))
        .Select(property => property.Name)
        .ToHashSet(StringComparer.OrdinalIgnoreCase);

    foreach (var target in targetsElement.EnumerateObject())
    {
        foreach (var library in target.Value.EnumerateObject())
        {
            if (!packageKeys.Contains(library.Name))
            {
                continue;
            }

            foreach (var sectionName in new[] { "compile", "runtime" })
            {
                if (!library.Value.TryGetProperty(sectionName, out var section))
                {
                    continue;
                }

                foreach (var asset in section.EnumerateObject())
                {
                    var assemblyName = Path.GetFileNameWithoutExtension(asset.Name);
                    if (!string.IsNullOrWhiteSpace(assemblyName) && !map.ContainsKey(assemblyName))
                    {
                        map[assemblyName] = $"nuget:{library.Name}";
                    }
                }
            }
        }
    }

    return map;
}

void EnsureMsBuildRegistered()
{
    if (!MSBuildLocator.IsRegistered)
    {
        MSBuildLocator.RegisterDefaults();
    }
}

bool IsProjectUnderRoot(string? projectFilePath, string repoRoot) =>
    !string.IsNullOrWhiteSpace(projectFilePath) && IsPathUnderRoot(projectFilePath, repoRoot);

bool IsPathUnderRoot(string path, string root)
{
    var fullPath = Path.GetFullPath(path)
        .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    var fullRoot = Path.GetFullPath(root)
        .TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    return fullPath.Equals(fullRoot, StringComparison.OrdinalIgnoreCase)
        || fullPath.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)
        || fullPath.StartsWith(fullRoot + Path.AltDirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
}

string FindAnalysisRootForFile(string filePath)
{
    var current = new DirectoryInfo(Path.GetDirectoryName(filePath) ?? throw new InvalidOperationException("Invalid C# file path."));
    while (current is not null)
    {
        if (current.EnumerateFiles("*.sln").Any()
            || current.EnumerateFiles("*.slnx").Any()
            || current.EnumerateFiles("*.csproj").Any())
        {
            return current.FullName;
        }

        current = current.Parent;
    }

    return Path.GetDirectoryName(filePath) ?? throw new InvalidOperationException("Invalid C# file path.");
}

IEnumerable<string> EnumerateFiles(string root, string pattern) =>
    Directory.EnumerateFiles(root, pattern, SearchOption.AllDirectories)
        .Where(path => !ShouldSkip(path));

bool ShouldSkip(string path)
{
    var segments = path.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    return segments.Any(segment => segment is "bin" or "obj" or ".git" or "node_modules" or ".venv");
}

string NormalizeRelativePath(string root, string path) =>
    Path.GetRelativePath(root, path).Replace('\\', '/');

int CountLoc(string text) => string.IsNullOrEmpty(text) ? 0 : text.Count(character => character == '\n') + 1;

bool IsFrameworkAssembly(string assemblyName) => assemblyName.StartsWith("System.", StringComparison.Ordinal)
    || assemblyName is "System" or "mscorlib" or "netstandard" or "Microsoft.CSharp";

HelperNode CreateExternalNode(string id)
{
    var type = id.StartsWith("nuget:", StringComparison.Ordinal) ? "package" : "assembly";
    return new HelperNode(id, type, "csharp", 0, 0, 0);
}

internal sealed record DocumentContext(
    string RelativePath,
    string AbsolutePath,
    SyntaxNode Root,
    SemanticModel SemanticModel,
    Project Project,
    Dictionary<string, string> PackageAssemblies,
    int Loc);

internal sealed record HelperAnalysis(
    List<HelperNode> Nodes,
    List<HelperNode> ExternalNodes,
    List<HelperLink> Links,
    List<HelperSymbol> Symbols,
    List<string> Diagnostics);

internal sealed record HelperPayload(
    [property: JsonPropertyName("schemaVersion")] int SchemaVersion,
    [property: JsonPropertyName("nodes")] List<HelperNode> Nodes,
    [property: JsonPropertyName("external_nodes")] List<HelperNode> ExternalNodes,
    [property: JsonPropertyName("links")] List<HelperLink> Links,
    [property: JsonPropertyName("symbols")] List<HelperSymbol> Symbols,
    [property: JsonPropertyName("meta")] HelperMeta Meta);

internal sealed record HelperMeta(
    [property: JsonPropertyName("sdkVersion")] string SdkVersion,
    [property: JsonPropertyName("helperVersion")] string HelperVersion,
    [property: JsonPropertyName("helperProtocolVersion")] string HelperProtocolVersion,
    [property: JsonPropertyName("diagnostics")] List<string> Diagnostics,
    [property: JsonPropertyName("timing")] HelperTiming Timing);

internal sealed record HelperTiming([property: JsonPropertyName("elapsedMs")] long ElapsedMs);

internal sealed record HelperSourceSpan(
    [property: JsonPropertyName("startLine")] int StartLine,
    [property: JsonPropertyName("startColumn")] int StartColumn,
    [property: JsonPropertyName("endLine")] int EndLine,
    [property: JsonPropertyName("endColumn")] int EndColumn);

internal sealed record HelperNode(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("type")] string Type,
    [property: JsonPropertyName("language")] string Language,
    [property: JsonPropertyName("size")] int Size,
    [property: JsonPropertyName("loc")] int Loc,
    [property: JsonPropertyName("imports")] int Imports);

internal sealed record HelperLink(
    [property: JsonPropertyName("source")] string Source,
    [property: JsonPropertyName("target")] string Target,
    [property: JsonPropertyName("weight")] int Weight,
    [property: JsonPropertyName("sourceSpan")] HelperSourceSpan? SourceSpan,
    [property: JsonPropertyName("symbol")] string? Symbol);

internal sealed record HelperSymbol(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("line")] int Line,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("exported")] bool Exported,
    [property: JsonPropertyName("methods")] List<string>? Methods,
    [property: JsonPropertyName("doc")] string? Doc,
    [property: JsonPropertyName("accessibility")] string Accessibility,
    [property: JsonPropertyName("signature")] string Signature,
    [property: JsonPropertyName("containingType")] string? ContainingType,
    [property: JsonPropertyName("sourceSpan")] HelperSourceSpan SourceSpan,
    [property: JsonPropertyName("file")] string File);

internal sealed class MutableLink
{
    public required string Source { get; init; }

    public required string Target { get; init; }

    public int Weight { get; set; }

    public HelperSourceSpan? SourceSpan { get; init; }

    public string? Symbol { get; init; }
}
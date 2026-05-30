using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

const string SupportedProtocolVersion = "1";
const int SchemaVersion = 1;

var started = Stopwatch.StartNew();
var parsedArgs = ParseArgs(args);

if (!parsedArgs.TryGetValue("file", out var filePath) || string.IsNullOrWhiteSpace(filePath))
{
    Console.Error.WriteLine("Missing required --file argument.");
    return 2;
}

var requestedProtocol = parsedArgs.GetValueOrDefault("protocol-version") ?? SupportedProtocolVersion;
if (!string.Equals(requestedProtocol, SupportedProtocolVersion, StringComparison.Ordinal))
{
    Console.Error.WriteLine(
        $"Unsupported helper protocol version '{requestedProtocol}'. Expected '{SupportedProtocolVersion}'.");
    return 2;
}

if (!File.Exists(filePath))
{
    Console.Error.WriteLine($"C# file not found: {filePath}");
    return 2;
}

string source;
try
{
    source = await File.ReadAllTextAsync(filePath);
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Failed to read C# file '{filePath}': {ex.Message}");
    return 2;
}

var tree = CSharpSyntaxTree.ParseText(source, path: filePath);
var root = await tree.GetRootAsync();
var symbols = ExtractSymbols(root);
var helperVersion =
    typeof(Program).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion
    ?? typeof(Program).Assembly.GetName().Version?.ToString()
    ?? "0.2.0";

var payload = new HelperPayload(
    SchemaVersion,
    new List<object>(),
    new List<object>(),
    new List<object>(),
    symbols,
    new HelperMeta(
        parsedArgs.GetValueOrDefault("sdk-version") ?? "unknown-sdk",
        helperVersion,
        SupportedProtocolVersion,
        new List<string>(),
        new HelperTiming(started.ElapsedMilliseconds)));

var options = new JsonSerializerOptions
{
    DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
};
Console.Out.Write(JsonSerializer.Serialize(payload, options));
return 0;

static Dictionary<string, string> ParseArgs(string[] args)
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

static List<HelperSymbol> ExtractSymbols(Microsoft.CodeAnalysis.SyntaxNode root)
{
    var symbols = new List<HelperSymbol>();
    var seen = new HashSet<string>(StringComparer.Ordinal);

    foreach (var typeDeclaration in root.DescendantNodes().OfType<BaseTypeDeclarationSyntax>())
    {
        if (!IsSymbolContainer(typeDeclaration.Parent))
        {
            continue;
        }

        var name = typeDeclaration switch
        {
            EnumDeclarationSyntax enumDeclaration => enumDeclaration.Identifier.ValueText,
            TypeDeclarationSyntax declaration => declaration.Identifier.ValueText,
            _ => string.Empty,
        };
        if (string.IsNullOrWhiteSpace(name) || !seen.Add(name))
        {
            continue;
        }

        symbols.Add(new HelperSymbol(
            name,
            LineNumber(typeDeclaration),
            TypeKind(typeDeclaration),
            IsExported(typeDeclaration.Modifiers),
            typeDeclaration is TypeDeclarationSyntax typeNode ? ExtractMethods(typeNode) : null,
            null));
    }

    foreach (var delegateDeclaration in root.DescendantNodes().OfType<DelegateDeclarationSyntax>())
    {
        if (!IsSymbolContainer(delegateDeclaration.Parent) || !seen.Add(delegateDeclaration.Identifier.ValueText))
        {
            continue;
        }

        symbols.Add(new HelperSymbol(
            delegateDeclaration.Identifier.ValueText,
            LineNumber(delegateDeclaration),
            "delegate",
            IsExported(delegateDeclaration.Modifiers),
            null,
            null));
    }

    foreach (var method in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
    {
        var name = method.Identifier.ValueText;
        if (string.IsNullOrWhiteSpace(name) || !seen.Add(name))
        {
            continue;
        }

        symbols.Add(new HelperSymbol(
            name,
            LineNumber(method),
            "function",
            IsExported(method.Modifiers),
            null,
            null));
    }

    return symbols;
}

static bool IsSymbolContainer(Microsoft.CodeAnalysis.SyntaxNode? node) =>
    node is CompilationUnitSyntax or NamespaceDeclarationSyntax or FileScopedNamespaceDeclarationSyntax;

static bool IsExported(Microsoft.CodeAnalysis.SyntaxTokenList modifiers) =>
    modifiers.Any(token => token.Kind() == SyntaxKind.PublicKeyword);

static int LineNumber(Microsoft.CodeAnalysis.SyntaxNode node) =>
    node.GetLocation().GetLineSpan().StartLinePosition.Line + 1;

static List<string>? ExtractMethods(TypeDeclarationSyntax declaration)
{
    var methods = declaration.Members
        .OfType<MethodDeclarationSyntax>()
        .Select(method => method.Identifier.ValueText)
        .Where(name => !string.IsNullOrWhiteSpace(name))
        .Distinct(StringComparer.Ordinal)
        .ToList();
    return methods.Count == 0 ? null : methods;
}

static string TypeKind(BaseTypeDeclarationSyntax declaration) => declaration switch
{
    ClassDeclarationSyntax => "class",
    StructDeclarationSyntax => "struct",
    InterfaceDeclarationSyntax => "interface",
    EnumDeclarationSyntax => "enum",
    RecordDeclarationSyntax recordDeclaration =>
        recordDeclaration.ClassOrStructKeyword.Kind() == SyntaxKind.StructKeyword ? "struct" : "class",
    _ => "class",
};

internal sealed record HelperPayload(
    [property: JsonPropertyName("schemaVersion")] int SchemaVersion,
    [property: JsonPropertyName("nodes")] List<object> Nodes,
    [property: JsonPropertyName("external_nodes")] List<object> ExternalNodes,
    [property: JsonPropertyName("links")] List<object> Links,
    [property: JsonPropertyName("symbols")] List<HelperSymbol> Symbols,
    [property: JsonPropertyName("meta")] HelperMeta Meta);

internal sealed record HelperMeta(
    [property: JsonPropertyName("sdkVersion")] string SdkVersion,
    [property: JsonPropertyName("helperVersion")] string HelperVersion,
    [property: JsonPropertyName("helperProtocolVersion")] string HelperProtocolVersion,
    [property: JsonPropertyName("diagnostics")] List<string> Diagnostics,
    [property: JsonPropertyName("timing")] HelperTiming Timing);

internal sealed record HelperTiming([property: JsonPropertyName("elapsedMs")] long ElapsedMs);

internal sealed record HelperSymbol(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("line")] int Line,
    [property: JsonPropertyName("kind")] string Kind,
    [property: JsonPropertyName("exported")] bool Exported,
    [property: JsonPropertyName("methods")] List<string>? Methods,
    [property: JsonPropertyName("doc")] string? Doc);
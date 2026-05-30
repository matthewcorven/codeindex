namespace RazorBlazorSpike.Shared;

public interface IWidget
{
    int Id { get; }
    string Title { get; }
    WidgetStatus Status { get; }
    IReadOnlyList<string> Tags { get; }
}

public enum WidgetStatus
{
    Ready,
    Blocked,
}
namespace RazorBlazorSpike.Pages;

using RazorBlazorSpike.Shared;

public partial class Dashboard<TItem> where TItem : IWidget
{
    public string Heading => $"Dashboard {AccountId}";
}
// The container's HEALTHCHECK executable. A chiseled runtime image has no shell and no
// curl (research.md R1), so this is the only way the image can have a HEALTHCHECK at all.
// It must not be able to fail for any reason other than the target endpoint's own status —
// no configuration, no logging, no telemetry — because a probe with dependencies of its own
// makes the container's health signal ambiguous.

if (args.Length != 1)
{
    Console.Error.WriteLine("usage: Identity.HealthProbe <url>");
    return 1;
}

using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };

try
{
    var response = await client.GetAsync(args[0]);
    if (response.IsSuccessStatusCode)
    {
        return 0;
    }

    Console.Error.WriteLine($"probe: {(int)response.StatusCode} {response.StatusCode}");
    return 1;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"probe: {ex.GetType().Name}: {ex.Message}");
    return 1;
}

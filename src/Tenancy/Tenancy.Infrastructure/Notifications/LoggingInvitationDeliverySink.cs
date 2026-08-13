using Microsoft.Extensions.Logging;
using Tenancy.Application.Invitations;
using Tenancy.Domain.Abstractions;

namespace Tenancy.Infrastructure.Notifications;

/// <summary>
/// The development-time stand-in for <see cref="IInvitationDeliverySink"/> (T080, Assumption 8):
/// a real email-sending implementation is out of scope for this slice, so this logs the
/// recipient and confirms an invitation was issued — following FR-025's established
/// templated-logging convention (T059's <c>TenantContextResolutionMiddleware</c>). Deliberately
/// never logs <paramref name="rawToken"/> — unlike a token *hash* (which T059/T072 already treat
/// carefully), the raw token is the literal, unhashed credential handed to the invitee; logging it
/// would put a live bearer-equivalent secret into log storage.
/// </summary>
/// <remarks>
/// Stateless: safe to register as a singleton (see <c>Program.cs</c>'s registration comment).
/// </remarks>
public sealed class LoggingInvitationDeliverySink : IInvitationDeliverySink
{
    private readonly ILogger<LoggingInvitationDeliverySink> _logger;

    public LoggingInvitationDeliverySink(ILogger<LoggingInvitationDeliverySink> logger)
    {
        _logger = logger;
    }

    /// <inheritdoc />
    public Task DeliverAsync(EmailAddress recipient, string rawToken, CancellationToken ct)
    {
        _logger.LogInformation(
            "Invitation issued and (dev-time) delivered to {Recipient}",
            recipient);

        return Task.CompletedTask;
    }
}

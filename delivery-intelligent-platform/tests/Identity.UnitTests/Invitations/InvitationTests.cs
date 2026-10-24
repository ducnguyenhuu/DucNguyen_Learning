using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Xunit;

namespace Identity.UnitTests.Invitations;

/// <summary>
/// Failing (red) unit tests specifying the public API of the not-yet-implemented
/// <see cref="Invitation"/> entity (Task 22, implemented in Task 23). These tests define the
/// contract:
/// - Static factory
///   <c>Invitation.Create(TenantId tenantId, EmailAddress email, Role role, string tokenHash, DateTimeOffset expiresAtUtc)</c>
///   creates a new, <see cref="InvitationStatus.Pending"/> invitation. Only the SHA-256 hash of
///   the invitation token is stored (<c>TokenHash</c>) — the raw token is a credential and is
///   never persisted; hashing is the caller's responsibility.
/// - <c>Invitation</c> implements <see cref="ITenantOwned"/> so it participates in the global
///   tenant query filter.
/// - <c>Accept(IClock clock)</c> transitions a <see cref="InvitationStatus.Pending"/>,
///   non-expired invitation to <see cref="InvitationStatus.Accepted"/>.
/// - <c>Accept(IClock clock)</c> on an invitation whose <c>clock.UtcNow</c> is past
///   <c>ExpiresAtUtc</c> throws <see cref="DomainException"/>.
///
///   DESIGN DECISION (see task-22-report.md for full rationale): expiry is modelled as a
///   LAZILY-COMPUTED check inside <c>Accept</c>/<c>Revoke</c> (comparing
///   <c>Status == Pending &amp;&amp; clock.UtcNow &gt; ExpiresAtUtc</c>), NOT as a stored
///   transition write. <c>Status</c> only becomes <see cref="InvitationStatus.Expired"/> via
///   these tests when the domain code explicitly chooses to write it — these tests assert the
///   simpler "throw without writing Expired" behavior. Task 23 must implement expiry this way;
///   if a stored/observable <c>Expired</c> transition is later required (e.g. for T036/T038
///   reads), that is a follow-up design change, not part of this contract.
/// - <c>Revoke()</c> transitions a <see cref="InvitationStatus.Pending"/> invitation to
///   <see cref="InvitationStatus.Revoked"/>.
/// - <c>Accept</c>/<c>Revoke</c> on an already-terminal (<c>Accepted</c>, <c>Revoked</c>, or
///   <c>Expired</c>) invitation throws <see cref="DomainException"/> — terminal states cannot be
///   re-entered or crossed into one another.
/// - Public properties: <c>Id</c> (<see cref="InvitationId"/>), <c>TenantId</c>
///   (<see cref="TenantId"/>), <c>Email</c> (<see cref="EmailAddress"/>), <c>Role</c>
///   (<see cref="Role"/>), <c>TokenHash</c> (<see cref="string"/>), <c>Status</c>
///   (<see cref="InvitationStatus"/>), <c>ExpiresAtUtc</c> (<see cref="DateTimeOffset"/>).
/// </summary>
public class InvitationTests
{
    private const string SampleTokenHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85";

    private sealed class FakeClock(DateTimeOffset utcNow) : IClock
    {
        public DateTimeOffset UtcNow { get; } = utcNow;
    }

    private static DateTimeOffset FutureExpiry() => new(2099, 1, 1, 0, 0, 0, TimeSpan.Zero);

    private static Invitation CreatePendingInvitation(
        TenantId? tenantId = null,
        EmailAddress? email = null,
        Role role = Role.Member,
        string tokenHash = SampleTokenHash,
        DateTimeOffset? expiresAtUtc = null)
    {
        return Invitation.Create(
            tenantId ?? TenantId.New(),
            email ?? new EmailAddress("invitee@example.com"),
            role,
            tokenHash,
            expiresAtUtc ?? FutureExpiry());
    }

    [Fact]
    public void Create_WithValidArguments_SucceedsAndIsPendingWithNonDefaultId()
    {
        var tenantId = TenantId.New();
        var email = new EmailAddress("invitee@example.com");
        var expiresAtUtc = FutureExpiry();

        var invitation = Invitation.Create(tenantId, email, Role.Member, SampleTokenHash, expiresAtUtc);

        invitation.Id.Should().NotBe(default(InvitationId));
        invitation.TenantId.Should().Be(tenantId);
        invitation.Email.Should().Be(email);
        invitation.Role.Should().Be(Role.Member);
        invitation.TokenHash.Should().Be(SampleTokenHash);
        invitation.Status.Should().Be(InvitationStatus.Pending);
        invitation.ExpiresAtUtc.Should().Be(expiresAtUtc);
    }

    [Fact]
    public void Invitation_ImplementsITenantOwned_ExposingTenantIdPassedToCreate()
    {
        var tenantId = TenantId.New();

        var invitation = CreatePendingInvitation(tenantId: tenantId);

        ((ITenantOwned)invitation).TenantId.Should().Be(tenantId);
    }

    [Fact]
    public void Accept_WhenPendingAndNotExpired_TransitionsToAccepted()
    {
        var invitation = CreatePendingInvitation(expiresAtUtc: FutureExpiry());
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 11, 12, 0, 0, TimeSpan.Zero));

        invitation.Accept(clock);

        invitation.Status.Should().Be(InvitationStatus.Accepted);
    }

    [Fact]
    public void Accept_WhenClockIsPastExpiresAtUtc_ThrowsDomainException()
    {
        var expiresAtUtc = new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);
        var invitation = CreatePendingInvitation(expiresAtUtc: expiresAtUtc);
        var clock = new FakeClock(expiresAtUtc.AddSeconds(1));

        Action act = () => invitation.Accept(clock);

        act.Should().Throw<DomainException>();
    }

    [Fact]
    public void Accept_WhenClockIsPastExpiresAtUtc_DoesNotWriteExpiredStatus()
    {
        // Documents the lazy-computed design choice: Accept throws on expiry without leaving a
        // stored Expired transition behind. Status remains Pending after the throw.
        var expiresAtUtc = new DateTimeOffset(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);
        var invitation = CreatePendingInvitation(expiresAtUtc: expiresAtUtc);
        var clock = new FakeClock(expiresAtUtc.AddSeconds(1));

        Action act = () => invitation.Accept(clock);
        act.Should().Throw<DomainException>();

        invitation.Status.Should().Be(InvitationStatus.Pending);
    }

    [Fact]
    public void Revoke_WhenPending_TransitionsToRevoked()
    {
        var invitation = CreatePendingInvitation();

        invitation.Revoke();

        invitation.Status.Should().Be(InvitationStatus.Revoked);
    }

    [Fact]
    public void Accept_WhenAlreadyRevoked_ThrowsDomainException()
    {
        var invitation = CreatePendingInvitation();
        invitation.Revoke();
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 11, 12, 0, 0, TimeSpan.Zero));

        Action act = () => invitation.Accept(clock);

        act.Should().Throw<DomainException>();
    }

    [Fact]
    public void Accept_WhenAlreadyAccepted_ThrowsDomainException()
    {
        var invitation = CreatePendingInvitation();
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 11, 12, 0, 0, TimeSpan.Zero));
        invitation.Accept(clock);

        Action act = () => invitation.Accept(clock);

        act.Should().Throw<DomainException>();
    }

    [Fact]
    public void Revoke_WhenAlreadyAccepted_ThrowsDomainException()
    {
        var invitation = CreatePendingInvitation();
        var clock = new FakeClock(new DateTimeOffset(2026, 8, 11, 12, 0, 0, TimeSpan.Zero));
        invitation.Accept(clock);

        Action act = () => invitation.Revoke();

        act.Should().Throw<DomainException>();
    }
}

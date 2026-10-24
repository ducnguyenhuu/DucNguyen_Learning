using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Invitations;
using Identity.Domain.Abstractions;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;
using Xunit;

namespace Identity.UnitTests.Invitations;

/// <summary>
/// Unit tests for <see cref="ListInvitations"/> (T073), using hand-rolled in-memory fakes
/// following <c>InviteMemberTests</c>' (T071) established convention.
/// </summary>
public class ListInvitationsTests
{
    private static readonly DateTimeOffset FixedNow = new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow { get; set; } = FixedNow;
    }

    private sealed class FakeInvitationRepository : IInvitationRepository
    {
        public List<Invitation> Invitations { get; } = [];

        public Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");

        public Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");

        public Task AddAsync(Invitation invitation, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");

        public Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");

        public Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");

        public Task<IReadOnlyList<Invitation>> GetAllPendingAsync(CancellationToken ct) =>
            Task.FromResult<IReadOnlyList<Invitation>>(Invitations);

        public Task<Invitation?> GetByIdAsync(InvitationId id, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");

        public Task SaveAsync(Invitation invitation, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListInvitationsTests.");
    }

    private static ListInvitations CreateUseCase(
        FakeInvitationRepository repository, FakeClock? clock = null) =>
        new(
            repository,
            clock ?? new FakeClock(),
            NullLogger<ListInvitations>.Instance);

    private static Invitation CreatePendingInvitation(EmailAddress email, DateTimeOffset expiresAtUtc) =>
        Invitation.Create(email, Role.Member, "some-hash", expiresAtUtc);

    [CoversRequirement("FR-014")]
    [Fact]
    public async Task ExecuteAsync_ReturnsPendingInvitations_WithStatusStillPending()
    {
        var repository = new FakeInvitationRepository();
        var invitation = CreatePendingInvitation(
            new EmailAddress("invitee@example.com"), FixedNow + TimeSpan.FromDays(7));
        repository.Invitations.Add(invitation);

        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().HaveCount(1);
        result[0].Id.Should().Be(invitation.Id);
        result[0].Email.Should().Be(invitation.Email);
        result[0].Role.Should().Be(invitation.Role);
        result[0].Status.Should().Be(InvitationStatus.Pending);
        result[0].ExpiresAtUtc.Should().Be(invitation.ExpiresAtUtc);
    }

    [Fact]
    public async Task ExecuteAsync_PastExpiry_ReportsDerivedExpiredStatus_WithoutMutatingStoredEntity()
    {
        var repository = new FakeInvitationRepository();
        var invitation = CreatePendingInvitation(
            new EmailAddress("expired@example.com"), FixedNow - TimeSpan.FromMinutes(1));
        repository.Invitations.Add(invitation);

        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().HaveCount(1);
        result[0].Status.Should().Be(InvitationStatus.Expired);

        // The stored entity itself is never mutated — expiry is derived, not swept.
        invitation.Status.Should().Be(InvitationStatus.Pending);
    }

    [Fact]
    public async Task ExecuteAsync_NoInvitations_ReturnsEmptyList()
    {
        var repository = new FakeInvitationRepository();
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().BeEmpty();
    }
}

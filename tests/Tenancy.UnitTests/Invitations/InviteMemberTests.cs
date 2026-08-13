using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Invitations;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Invitations;
using Xunit;

namespace Tenancy.UnitTests.Invitations;

/// <summary>
/// Unit tests for <see cref="InviteMember"/> (T071), using hand-rolled in-memory fakes of
/// <see cref="IInvitationRepository"/>/<see cref="ITenantContext"/>/<see cref="IClock"/> —
/// following <c>CreateTenantTests</c>' (T054) established convention. No real database is needed
/// to verify this use case's own logic (the two 409 pre-checks, the 7-day expiry math, and the
/// raw-token-returned-once contract); whether the persistence layer actually enforces the
/// database-level unique-constraint race backstop is an Infrastructure-level concern, not this
/// use case's.
/// </summary>
public class InviteMemberTests
{
    private static readonly TenantId TestTenantId = new(Guid.CreateVersion7());
    private static readonly DateTimeOffset FixedNow = new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow { get; set; } = FixedNow;
    }

    private sealed class FakeTenantContext : ITenantContext
    {
        public TenantId TenantId { get; set; } = TestTenantId;

        public Role Role { get; set; } = Role.Administrator;
    }

    private sealed class FakeInvitationRepository : IInvitationRepository
    {
        public bool IsActiveMember { get; set; }

        public bool HasPendingInvitation { get; set; }

        /// <summary>When set, <see cref="AddAsync"/> throws this once, then clears itself — used
        /// to simulate losing the insert race against a concurrent invite.</summary>
        public DbUpdateException? ThrowOnAdd { get; set; }

        public Invitation? SavedInvitation { get; private set; }

        public Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct) =>
            Task.FromResult(IsActiveMember);

        public Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct) =>
            Task.FromResult(HasPendingInvitation);

        public Task AddAsync(Invitation invitation, CancellationToken ct)
        {
            if (ThrowOnAdd is { } exception)
            {
                ThrowOnAdd = null;
                throw exception;
            }

            SavedInvitation = invitation;
            return Task.CompletedTask;
        }

        public Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct) =>
            throw new NotSupportedException("Not used by InviteMemberTests.");

        public Task SaveAcceptedAsync(Invitation invitation, Tenancy.Domain.Memberships.Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by InviteMemberTests.");
    }

    private static InviteMember CreateUseCase(
        FakeInvitationRepository repository, FakeTenantContext? tenantContext = null, FakeClock? clock = null) =>
        new(
            repository,
            tenantContext ?? new FakeTenantContext(),
            clock ?? new FakeClock(),
            NullLogger<InviteMember>.Instance);

    [Fact]
    public async Task ExecuteAsync_HappyPath_CreatesPendingInvitationWithSevenDayExpiry_AndReturnsRawTokenOnce()
    {
        var repository = new FakeInvitationRepository();
        var clock = new FakeClock();
        var useCase = CreateUseCase(repository, clock: clock);
        var email = new EmailAddress("invitee@example.com");
        var invitedByUserId = UserId.New();

        var result = await useCase.ExecuteAsync(email, Role.Member, invitedByUserId, CancellationToken.None);

        result.Invitation.Should().BeSameAs(repository.SavedInvitation);
        result.Invitation.TenantId.Should().Be(TestTenantId);
        result.Invitation.Email.Should().Be(email);
        result.Invitation.Role.Should().Be(Role.Member);
        result.Invitation.Status.Should().Be(InvitationStatus.Pending);
        result.Invitation.ExpiresAtUtc.Should().Be(clock.UtcNow + TimeSpan.FromDays(7));

        result.RawToken.Should().NotBeNullOrWhiteSpace();

        // The persisted hash must never equal the raw token, and must match Hash(rawToken).
        result.Invitation.TokenHash.Should().Be(Convert.ToBase64String(InvitationToken.Hash(result.RawToken)));
        result.Invitation.TokenHash.Should().NotBe(result.RawToken);
    }

    [Fact]
    public async Task ExecuteAsync_AlreadyActiveMember_ThrowsConflictException_AndNeverPersists()
    {
        var repository = new FakeInvitationRepository { IsActiveMember = true };
        var useCase = CreateUseCase(repository);

        var act = () => useCase.ExecuteAsync(
            new EmailAddress("member@example.com"), Role.Member, UserId.New(), CancellationToken.None);

        await act.Should().ThrowAsync<ConflictException>();
        repository.SavedInvitation.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_AlreadyHasPendingInvitation_ThrowsConflictException_AndNeverPersists()
    {
        var repository = new FakeInvitationRepository { HasPendingInvitation = true };
        var useCase = CreateUseCase(repository);

        var act = () => useCase.ExecuteAsync(
            new EmailAddress("invitee@example.com"), Role.Member, UserId.New(), CancellationToken.None);

        await act.Should().ThrowAsync<ConflictException>();
        repository.SavedInvitation.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_LosesInsertRaceAgainstConcurrentInvite_ThrowsConflictException()
    {
        var repository = new FakeInvitationRepository
        {
            ThrowOnAdd = new DbUpdateException("simulated unique-constraint violation"),
        };
        var useCase = CreateUseCase(repository);

        var act = () => useCase.ExecuteAsync(
            new EmailAddress("invitee@example.com"), Role.Member, UserId.New(), CancellationToken.None);

        await act.Should().ThrowAsync<ConflictException>();
    }
}

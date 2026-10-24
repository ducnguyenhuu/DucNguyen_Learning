using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Invitations;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Invitations;
using Xunit;

namespace Identity.UnitTests.Invitations;

/// <summary>
/// Unit tests for <see cref="InviteMember"/>, using hand-rolled in-memory fakes of
/// <see cref="IInvitationRepository"/>/<see cref="IClock"/>. No real database is needed
/// to verify this use case's own logic (the two 409 pre-checks, the 7-day expiry math, and the
/// raw-token-returned-once contract); whether the persistence layer actually enforces the
/// database-level unique-constraint race backstop is an Infrastructure-level concern, not this
/// use case's.
/// </summary>
public class InviteMemberTests
{
    private static readonly DateTimeOffset FixedNow = new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow { get; set; } = FixedNow;
    }

    private sealed class FakeInvitationRepository : IInvitationRepository
    {
        public bool IsActiveMember { get; set; }

        public bool HasPendingInvitation { get; set; }

        /// <summary>When set, <see cref="AddAsync"/> throws this once, then clears itself — used
        /// to simulate losing the insert race against a concurrent invite.</summary>
        public ConcurrencyConflictException? ThrowOnAdd { get; set; }

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

        public Task SaveAcceptedAsync(Invitation invitation, Identity.Domain.Memberships.Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by InviteMemberTests.");

        public Task<IReadOnlyList<Invitation>> GetAllPendingAsync(CancellationToken ct) =>
            throw new NotSupportedException("Not used by InviteMemberTests.");

        public Task<Invitation?> GetByIdAsync(InvitationId id, CancellationToken ct) =>
            throw new NotSupportedException("Not used by InviteMemberTests.");

        public Task SaveAsync(Invitation invitation, CancellationToken ct) =>
            throw new NotSupportedException("Not used by InviteMemberTests.");
    }

    private sealed class FakeInvitationDeliverySink : IInvitationDeliverySink
    {
        public int CallCount { get; private set; }

        public EmailAddress? LastRecipient { get; private set; }

        public string? LastRawToken { get; private set; }

        public Task DeliverAsync(EmailAddress recipient, string rawToken, CancellationToken ct)
        {
            CallCount++;
            LastRecipient = recipient;
            LastRawToken = rawToken;
            return Task.CompletedTask;
        }
    }

    private sealed class FakeAuditWriter : IAuditWriter
    {
        public List<AuditEntry> RecordedEntries { get; } = [];

        public Task RecordAsync(AuditEntry entry, CancellationToken ct)
        {
            RecordedEntries.Add(entry);
            return Task.CompletedTask;
        }

        public Task RecordAndSaveAsync(AuditEntry entry, CancellationToken ct) =>
            throw new NotSupportedException("Not used by this test suite; only RecordAsync is exercised.");
    }

    private static InviteMember CreateUseCase(
        FakeInvitationRepository repository,
        FakeClock? clock = null,
        FakeInvitationDeliverySink? deliverySink = null,
        FakeAuditWriter? auditWriter = null) =>
        new(
            repository,
            clock ?? new FakeClock(),
            deliverySink ?? new FakeInvitationDeliverySink(),
            auditWriter ?? new FakeAuditWriter(),
            NullLogger<InviteMember>.Instance);

    [CoversRequirement("FR-011")]
    [Fact]
    public async Task ExecuteAsync_HappyPath_CreatesPendingInvitationWithSevenDayExpiry_AndReturnsRawTokenOnce()
    {
        var repository = new FakeInvitationRepository();
        var clock = new FakeClock();
        var deliverySink = new FakeInvitationDeliverySink();
        var useCase = CreateUseCase(repository, clock: clock, deliverySink: deliverySink);
        var email = new EmailAddress("invitee@example.com");
        var invitedByUserId = UserId.New();

        var result = await useCase.ExecuteAsync(email, Role.Member, invitedByUserId, CancellationToken.None);

        result.Invitation.Should().BeSameAs(repository.SavedInvitation);
        result.Invitation.Email.Should().Be(email);
        result.Invitation.Role.Should().Be(Role.Member);
        result.Invitation.Status.Should().Be(InvitationStatus.Pending);
        result.Invitation.ExpiresAtUtc.Should().Be(clock.UtcNow + TimeSpan.FromDays(7));

        result.RawToken.Should().NotBeNullOrWhiteSpace();

        // The persisted hash must never equal the raw token, and must match Hash(rawToken).
        result.Invitation.TokenHash.Should().Be(Convert.ToBase64String(InvitationToken.Hash(result.RawToken)));
        result.Invitation.TokenHash.Should().NotBe(result.RawToken);

        // Delivery is attempted exactly once, after persistence, with the recipient and
        // the real raw token (the same one returned to the caller above) — not the persisted hash.
        deliverySink.CallCount.Should().Be(1);
        deliverySink.LastRecipient.Should().Be(email);
        deliverySink.LastRawToken.Should().Be(result.RawToken);
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
            ThrowOnAdd = new ConcurrencyConflictException("simulated unique-constraint violation"),
        };
        var useCase = CreateUseCase(repository);

        var act = () => useCase.ExecuteAsync(
            new EmailAddress("invitee@example.com"), Role.Member, UserId.New(), CancellationToken.None);

        await act.Should().ThrowAsync<ConflictException>();
    }
}

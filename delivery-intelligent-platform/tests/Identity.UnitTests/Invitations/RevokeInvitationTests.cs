using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Invitations;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;
using Xunit;

namespace Identity.UnitTests.Invitations;

/// <summary>
/// Unit tests for <see cref="RevokeInvitation"/>, using hand-rolled in-memory fakes
/// following the established convention from <c>InviteMemberTests</c>.
/// </summary>
public class RevokeInvitationTests
{
    private static readonly DateTimeOffset FixedNow = new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);

    private sealed class FakeInvitationRepository : IInvitationRepository
    {
        public Invitation? StoredInvitation { get; set; }

        public Invitation? SavedInvitation { get; private set; }

        public Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct) =>
            throw new NotSupportedException("Not used by RevokeInvitationTests.");

        public Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct) =>
            throw new NotSupportedException("Not used by RevokeInvitationTests.");

        public Task AddAsync(Invitation invitation, CancellationToken ct) =>
            throw new NotSupportedException("Not used by RevokeInvitationTests.");

        public Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct) =>
            throw new NotSupportedException("Not used by RevokeInvitationTests.");

        public Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by RevokeInvitationTests.");

        public Task<IReadOnlyList<Invitation>> GetAllPendingAsync(CancellationToken ct) =>
            throw new NotSupportedException("Not used by RevokeInvitationTests.");

        public Task<Invitation?> GetByIdAsync(InvitationId id, CancellationToken ct) =>
            Task.FromResult(StoredInvitation is not null && StoredInvitation.Id == id ? StoredInvitation : null);

        public Task SaveAsync(Invitation invitation, CancellationToken ct)
        {
            SavedInvitation = invitation;
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

    private static RevokeInvitation CreateUseCase(
        FakeInvitationRepository repository, FakeAuditWriter? auditWriter = null) =>
        new(
            repository,
            auditWriter ?? new FakeAuditWriter(),
            new FixedClock(),
            NullLogger<RevokeInvitation>.Instance);

    private static Invitation CreatePendingInvitation() =>
        Invitation.Create(
            new EmailAddress("invitee@example.com"),
            Role.Member,
            "some-hash",
            FixedNow + TimeSpan.FromDays(7));

    [CoversRequirement("FR-014")]
    [Fact]
    public async Task ExecuteAsync_HappyPath_TransitionsToRevoked_AndSaves()
    {
        var invitation = CreatePendingInvitation();
        var repository = new FakeInvitationRepository { StoredInvitation = invitation };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(invitation.Id, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RevokeInvitationResultKind.Success);
        invitation.Status.Should().Be(InvitationStatus.Revoked);
        repository.SavedInvitation.Should().BeSameAs(invitation);
    }

    [Fact]
    public async Task ExecuteAsync_UnknownId_ReturnsNotFound_AndNeverSaves()
    {
        var repository = new FakeInvitationRepository();
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(InvitationId.New(), UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RevokeInvitationResultKind.NotFound);
        repository.SavedInvitation.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_AlreadyAccepted_ReturnsConflict_AndNeverSaves()
    {
        var invitation = CreatePendingInvitation();
        invitation.Accept(new FixedClock());
        var repository = new FakeInvitationRepository { StoredInvitation = invitation };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(invitation.Id, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RevokeInvitationResultKind.Conflict);
        invitation.Status.Should().Be(InvitationStatus.Accepted);
        repository.SavedInvitation.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_AlreadyRevoked_ReturnsConflict_AndNeverSaves()
    {
        var invitation = CreatePendingInvitation();
        invitation.Revoke();
        var repository = new FakeInvitationRepository { StoredInvitation = invitation };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(invitation.Id, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RevokeInvitationResultKind.Conflict);
        repository.SavedInvitation.Should().BeNull();
    }

    private sealed class FixedClock : IClock
    {
        public DateTimeOffset UtcNow => FixedNow;
    }
}

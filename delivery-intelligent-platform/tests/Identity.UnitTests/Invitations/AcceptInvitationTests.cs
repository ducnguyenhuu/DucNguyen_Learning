using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Invitations;
using Identity.Application.Users;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Invitations;
using Identity.Domain.Memberships;
using Identity.Domain.Users;
using Xunit;

namespace Identity.UnitTests.Invitations;

/// <summary>
/// Unit tests for <see cref="AcceptInvitation"/>, using hand-rolled in-memory fakes of
/// <see cref="IInvitationRepository"/>/<see cref="IUserRepository"/>/<see cref="IClock"/> —
/// following the established convention from <c>InviteMemberTests</c>.
/// </summary>
public class AcceptInvitationTests
{
    private static readonly DateTimeOffset FixedNow = new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);
    private static readonly EmailAddress InviteeEmail = new("invitee@example.com");
    private const string RawToken = "some-raw-token-value";

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow { get; set; } = FixedNow;
    }

    private sealed class FakeInvitationRepository : IInvitationRepository
    {
        public Invitation? StoredInvitation { get; set; }

        public Invitation? SavedInvitation { get; private set; }

        public Membership? SavedMembership { get; private set; }

        public bool IsActiveMember { get; set; }

        public Task<bool> IsActiveMemberAsync(EmailAddress email, CancellationToken ct) =>
            Task.FromResult(IsActiveMember);

        public Task<bool> HasPendingInvitationAsync(EmailAddress email, CancellationToken ct) =>
            Task.FromResult(false);

        public Task AddAsync(Invitation invitation, CancellationToken ct) => Task.CompletedTask;

        public Task<Invitation?> FindByTokenHashAsync(string tokenHashBase64, CancellationToken ct)
        {
            if (StoredInvitation is not null &&
                StoredInvitation.TokenHash == tokenHashBase64)
            {
                return Task.FromResult<Invitation?>(StoredInvitation);
            }

            return Task.FromResult<Invitation?>(null);
        }

        public Task SaveAcceptedAsync(Invitation invitation, Membership membership, CancellationToken ct)
        {
            SavedInvitation = invitation;
            SavedMembership = membership;
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<Invitation>> GetAllPendingAsync(CancellationToken ct) =>
            throw new NotSupportedException("Not used by AcceptInvitationTests.");

        public Task<Invitation?> GetByIdAsync(InvitationId id, CancellationToken ct) =>
            throw new NotSupportedException("Not used by AcceptInvitationTests.");

        public Task SaveAsync(Invitation invitation, CancellationToken ct) =>
            throw new NotSupportedException("Not used by AcceptInvitationTests.");
    }

    private sealed class FakeUserRepository : IUserRepository
    {
        public User? ExistingUser { get; set; }

        public Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct) =>
            Task.FromResult(ExistingUser);

        public Task AddAsync(User user, CancellationToken ct)
        {
            ExistingUser = user;
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct) =>
            throw new NotSupportedException("Not used by AcceptInvitationTests.");
    }

    private static Invitation CreatePendingInvitation(
        EmailAddress email, DateTimeOffset expiresAtUtc, string rawToken = RawToken)
    {
        var tokenHash = Convert.ToBase64String(InvitationToken.Hash(rawToken));
        return Invitation.Create(email, Role.Member, tokenHash, expiresAtUtc);
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

    private static AcceptInvitation CreateUseCase(
        FakeInvitationRepository invitationRepository,
        FakeUserRepository? userRepository = null,
        FakeClock? clock = null,
        FakeAuditWriter? auditWriter = null) =>
        new(
            invitationRepository,
            new EnsureUserProvisioned(userRepository ?? new FakeUserRepository()),
            clock ?? new FakeClock(),
            auditWriter ?? new FakeAuditWriter(),
            NullLogger<AcceptInvitation>.Instance);

    [CoversRequirement("FR-012")]
    [Fact]
    public async Task ExecuteAsync_HappyPath_CreatesMembership_MarksInvitationAccepted_ReturnsSuccess()
    {
        var invitationRepository = new FakeInvitationRepository
        {
            StoredInvitation = CreatePendingInvitation(InviteeEmail, FixedNow + TimeSpan.FromDays(1)),
        };
        var useCase = CreateUseCase(invitationRepository);

        var result = await useCase.ExecuteAsync(
            RawToken, Guid.NewGuid(), Guid.NewGuid(), InviteeEmail, CancellationToken.None);

        result.Kind.Should().Be(AcceptInvitationResultKind.Success);
        result.Membership.Should().NotBeNull();
        result.Membership!.Role.Should().Be(Role.Member);

        invitationRepository.SavedInvitation.Should().NotBeNull();
        invitationRepository.SavedInvitation!.Status.Should().Be(InvitationStatus.Accepted);
        invitationRepository.SavedMembership.Should().BeSameAs(result.Membership);
    }

    [CoversRequirement("FR-013")]
    [Fact]
    public async Task ExecuteAsync_UnknownToken_ReturnsNotFound()
    {
        var invitationRepository = new FakeInvitationRepository();
        var useCase = CreateUseCase(invitationRepository);

        var result = await useCase.ExecuteAsync(
            "unknown-token", Guid.NewGuid(), Guid.NewGuid(), InviteeEmail, CancellationToken.None);

        result.Kind.Should().Be(AcceptInvitationResultKind.NotFound);
        invitationRepository.SavedInvitation.Should().BeNull();
    }

    [CoversRequirement("FR-013")]
    [Fact]
    public async Task ExecuteAsync_ExpiredToken_ReturnsNotAcceptable()
    {
        var invitationRepository = new FakeInvitationRepository
        {
            StoredInvitation = CreatePendingInvitation(InviteeEmail, FixedNow - TimeSpan.FromMinutes(1)),
        };
        var useCase = CreateUseCase(invitationRepository);

        var result = await useCase.ExecuteAsync(
            RawToken, Guid.NewGuid(), Guid.NewGuid(), InviteeEmail, CancellationToken.None);

        result.Kind.Should().Be(AcceptInvitationResultKind.NotAcceptable);
        invitationRepository.SavedInvitation.Should().BeNull();
    }

    [CoversRequirement("FR-013")]
    [Fact]
    public async Task ExecuteAsync_AlreadyAcceptedToken_ReturnsNotAcceptable()
    {
        var invitation = CreatePendingInvitation(InviteeEmail, FixedNow + TimeSpan.FromDays(1));
        invitation.Accept(new FakeClock { UtcNow = FixedNow });
        var invitationRepository = new FakeInvitationRepository { StoredInvitation = invitation };
        var useCase = CreateUseCase(invitationRepository);

        var result = await useCase.ExecuteAsync(
            RawToken, Guid.NewGuid(), Guid.NewGuid(), InviteeEmail, CancellationToken.None);

        result.Kind.Should().Be(AcceptInvitationResultKind.NotAcceptable);
    }

    [CoversRequirement("FR-013")]
    [Fact]
    public async Task ExecuteAsync_WrongIdentity_ReturnsWrongIdentity_AndDoesNotAcceptInvitation()
    {
        var invitation = CreatePendingInvitation(InviteeEmail, FixedNow + TimeSpan.FromDays(1));
        var invitationRepository = new FakeInvitationRepository { StoredInvitation = invitation };
        var useCase = CreateUseCase(invitationRepository);

        var result = await useCase.ExecuteAsync(
            RawToken, Guid.NewGuid(), Guid.NewGuid(), new EmailAddress("someone-else@example.com"), CancellationToken.None);

        result.Kind.Should().Be(AcceptInvitationResultKind.WrongIdentity);
        invitation.Status.Should().Be(InvitationStatus.Pending);
        invitationRepository.SavedInvitation.Should().BeNull();
    }

    [CoversRequirement("FR-012")]
    [Fact]
    public async Task ExecuteAsync_CallerAlreadyActiveMember_ReturnsAlreadyMember_AndLeavesInvitationPending()
    {
        var invitation = CreatePendingInvitation(InviteeEmail, FixedNow + TimeSpan.FromDays(1));
        var invitationRepository = new FakeInvitationRepository
        {
            StoredInvitation = invitation,
            IsActiveMember = true,
        };
        var useCase = CreateUseCase(invitationRepository);

        var result = await useCase.ExecuteAsync(
            RawToken, Guid.NewGuid(), Guid.NewGuid(), InviteeEmail, CancellationToken.None);

        result.Kind.Should().Be(AcceptInvitationResultKind.AlreadyMember);
        invitation.Status.Should().Be(InvitationStatus.Pending);
        invitationRepository.SavedMembership.Should().BeNull();
    }
}

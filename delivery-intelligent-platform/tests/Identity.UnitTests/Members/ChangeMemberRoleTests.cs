using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Members;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Memberships;
using Xunit;

namespace Identity.UnitTests.Members;

/// <summary>
/// Unit tests for <see cref="ChangeMemberRole"/>, using hand-rolled in-memory fakes
/// following the established convention from <c>RemoveMemberTests</c>.
/// </summary>
public class ChangeMemberRoleTests
{
    private sealed class FakeMembershipRepository : IMembershipRepository
    {
        public Membership? ActiveMembership { get; set; }

        public IReadOnlyList<Membership> ActiveMemberships { get; set; } = [];

        public Membership? Saved { get; private set; }

        public Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct) =>
            Task.FromResult(ActiveMemberships);

        public Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct) =>
            Task.FromResult(ActiveMembership is not null && ActiveMembership.UserId == userId
                ? ActiveMembership
                : null);

        public Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ChangeMemberRoleTests.");

        public Task<bool> TryAddFirstAdministratorAsync(Membership administratorMembership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ChangeMemberRoleTests.");

        public Task SaveAsync(Membership membership, CancellationToken ct)
        {
            Saved = membership;
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

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow => new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);
    }

    private static ChangeMemberRole CreateUseCase(FakeMembershipRepository repository) =>
        new(repository, new FakeAuditWriter(), new FakeClock(), NullLogger<ChangeMemberRole>.Instance);

    [CoversRequirement("FR-014")]
    [Fact]
    public async Task ExecuteAsync_HappyPath_ChangesRoleAndSaves()
    {
        var targetUserId = UserId.New();
        var membership = Membership.Create(targetUserId, Role.Member);
        var otherAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var repository = new FakeMembershipRepository
        {
            ActiveMembership = membership,
            ActiveMemberships = [membership, otherAdministrator],
        };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(
            targetUserId, Role.Administrator, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(ChangeMemberRoleResultKind.Success);
        membership.Role.Should().Be(Role.Administrator);
        repository.Saved.Should().Be(membership);
    }

    [Fact]
    public async Task ExecuteAsync_UnknownUserId_ReturnsNotFound_AndNeverSaves()
    {
        var repository = new FakeMembershipRepository();
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(
            UserId.New(), Role.Administrator, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(ChangeMemberRoleResultKind.NotFound);
        repository.Saved.Should().BeNull();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public async Task ExecuteAsync_LastAdministrator_ReturnsConflict_AndNeverSaves()
    {
        var targetUserId = UserId.New();
        var membership = Membership.Create(targetUserId, Role.Administrator);
        var repository = new FakeMembershipRepository
        {
            ActiveMembership = membership,
            ActiveMemberships = [membership],
        };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(
            targetUserId, Role.Member, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(ChangeMemberRoleResultKind.Conflict);
        membership.Role.Should().Be(Role.Administrator);
        repository.Saved.Should().BeNull();
    }
}

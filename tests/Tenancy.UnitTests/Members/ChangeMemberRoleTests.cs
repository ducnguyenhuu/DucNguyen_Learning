using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Members;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Xunit;

namespace Tenancy.UnitTests.Members;

/// <summary>
/// Unit tests for <see cref="ChangeMemberRole"/> (T086), using hand-rolled in-memory fakes
/// following <c>RemoveMemberTests</c>' (T076) established convention.
/// </summary>
public class ChangeMemberRoleTests
{
    private static readonly TenantId TestTenantId = new(Guid.CreateVersion7());

    private sealed class FakeTenantContext : ITenantContext
    {
        public TenantId TenantId { get; set; } = TestTenantId;

        public Role Role { get; set; } = Role.Administrator;
    }

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

        public Task SaveAsync(Membership membership, CancellationToken ct)
        {
            Saved = membership;
            return Task.CompletedTask;
        }
    }

    private static ChangeMemberRole CreateUseCase(FakeMembershipRepository repository) =>
        new(repository, new FakeTenantContext(), NullLogger<ChangeMemberRole>.Instance);

    [CoversRequirement("FR-014")]
    [Fact]
    public async Task ExecuteAsync_HappyPath_ChangesRoleAndSaves()
    {
        var targetUserId = UserId.New();
        var membership = Membership.Create(TestTenantId, targetUserId, Role.Member);
        var otherAdministrator = Membership.Create(TestTenantId, UserId.New(), Role.Administrator);
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
        var membership = Membership.Create(TestTenantId, targetUserId, Role.Administrator);
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

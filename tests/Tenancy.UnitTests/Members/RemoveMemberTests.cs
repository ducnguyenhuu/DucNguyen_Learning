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
/// Unit tests for <see cref="RemoveMember"/> (T076), using hand-rolled in-memory fakes following
/// <c>RevokeInvitationTests</c>' (T073) established convention.
/// </summary>
public class RemoveMemberTests
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

        public MembershipId? RemovedMembershipId { get; private set; }

        public Exception? ThrowOnRemove { get; set; }

        public Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct) =>
            throw new NotSupportedException("Not used by RemoveMemberTests.");

        public Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct) =>
            Task.FromResult(ActiveMembership is not null && ActiveMembership.UserId == userId
                ? ActiveMembership
                : null);

        public Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct)
        {
            if (ThrowOnRemove is not null)
            {
                throw ThrowOnRemove;
            }

            RemovedMembershipId = membershipId;
            return Task.CompletedTask;
        }

        public Task SaveAsync(Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by RemoveMemberTests.");
    }

    private static RemoveMember CreateUseCase(FakeMembershipRepository repository) =>
        new(repository, new FakeTenantContext(), NullLogger<RemoveMember>.Instance);

    [CoversRequirement("FR-014")]
    [Fact]
    public async Task ExecuteAsync_HappyPath_RemovesMembership()
    {
        var targetUserId = UserId.New();
        var membership = Membership.Create(TestTenantId, targetUserId, Role.Member);
        var repository = new FakeMembershipRepository { ActiveMembership = membership };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(targetUserId, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RemoveMemberResultKind.Success);
        repository.RemovedMembershipId.Should().Be(membership.Id);
    }

    [Fact]
    public async Task ExecuteAsync_UnknownUserId_ReturnsNotFound_AndNeverRemoves()
    {
        var repository = new FakeMembershipRepository();
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(UserId.New(), UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RemoveMemberResultKind.NotFound);
        repository.RemovedMembershipId.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_InactiveUserId_ReturnsNotFound()
    {
        var targetUserId = UserId.New();
        // ActiveMembership left unset — mirrors "no active membership" for this user, whether
        // never a member or already removed; GetActiveMembershipForUserAsync's contract collapses
        // both to null.
        var repository = new FakeMembershipRepository();
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(targetUserId, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RemoveMemberResultKind.NotFound);
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public async Task ExecuteAsync_LastAdministrator_ReturnsConflict()
    {
        var targetUserId = UserId.New();
        var membership = Membership.Create(TestTenantId, targetUserId, Role.Administrator);
        var repository = new FakeMembershipRepository
        {
            ActiveMembership = membership,
            ThrowOnRemove = new DomainException("Cannot remove the last administrator."),
        };
        var useCase = CreateUseCase(repository);

        var result = await useCase.ExecuteAsync(targetUserId, UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(RemoveMemberResultKind.Conflict);
        repository.RemovedMembershipId.Should().BeNull();
    }
}

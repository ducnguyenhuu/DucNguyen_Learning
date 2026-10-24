using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Members;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Users;
using Xunit;

namespace Identity.UnitTests.Members;

/// <summary>
/// Unit tests for <see cref="ListMembers"/> (T076), using hand-rolled in-memory fakes following
/// <c>RevokeInvitationTests</c>' (T073) established convention.
/// </summary>
public class ListMembersTests
{
    private static readonly TenantId TestTenantId = new(Guid.CreateVersion7());

    private sealed class FakeTenantContext : ITenantContext
    {
        public TenantId TenantId { get; set; } = TestTenantId;

        public Role Role { get; set; } = Role.Administrator;
    }

    private sealed class FakeMembershipRepository : IMembershipRepository
    {
        public List<Membership> ActiveMembers { get; } = [];

        public Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct) =>
            Task.FromResult((IReadOnlyList<Membership>)ActiveMembers);

        public Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListMembersTests.");

        public Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListMembersTests.");

        public Task SaveAsync(Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListMembersTests.");
    }

    private sealed class FakeUserRepository : IUserRepository
    {
        public List<User> Users { get; } = [];

        public Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListMembersTests.");

        public Task AddAsync(User user, CancellationToken ct) =>
            throw new NotSupportedException("Not used by ListMembersTests.");

        public Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct) =>
            Task.FromResult((IReadOnlyList<User>)Users.Where(u => userIds.Contains(u.Id)).ToList());
    }

    private static ListMembers CreateUseCase(
        FakeMembershipRepository membershipRepository, FakeUserRepository userRepository) =>
        new(membershipRepository, userRepository, new FakeTenantContext(), NullLogger<ListMembers>.Instance);

    [CoversRequirement("FR-014")]
    [Fact]
    public async Task ExecuteAsync_ReturnsActiveMembers_WithResolvedEmails()
    {
        var user = User.Create(Guid.NewGuid(), Guid.NewGuid(), new EmailAddress("member@example.com"));
        var membership = Membership.Create(TestTenantId, user.Id, Role.Member);

        var membershipRepository = new FakeMembershipRepository();
        membershipRepository.ActiveMembers.Add(membership);
        var userRepository = new FakeUserRepository();
        userRepository.Users.Add(user);

        var useCase = CreateUseCase(membershipRepository, userRepository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().ContainSingle();
        result[0].UserId.Should().Be(user.Id);
        result[0].Email.Should().Be(user.Email);
        result[0].Role.Should().Be(Role.Member);
        result[0].Status.Should().Be(MembershipStatus.Active);
    }

    [Fact]
    public async Task ExecuteAsync_NoActiveMembers_ReturnsEmpty()
    {
        var membershipRepository = new FakeMembershipRepository();
        var userRepository = new FakeUserRepository();
        var useCase = CreateUseCase(membershipRepository, userRepository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().BeEmpty();
    }

    [Fact]
    public async Task ExecuteAsync_MissingUserRow_ReturnsNullEmail()
    {
        var membership = Membership.Create(TestTenantId, UserId.New(), Role.Member);
        var membershipRepository = new FakeMembershipRepository();
        membershipRepository.ActiveMembers.Add(membership);
        var userRepository = new FakeUserRepository();

        var useCase = CreateUseCase(membershipRepository, userRepository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().ContainSingle();
        result[0].Email.Should().BeNull();
    }
}

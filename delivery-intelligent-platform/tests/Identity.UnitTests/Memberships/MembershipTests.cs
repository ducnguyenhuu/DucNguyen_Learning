using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Xunit;

namespace Identity.UnitTests.Memberships;

/// <summary>
/// Failing (red) unit tests specifying the public API of the not-yet-implemented
/// <see cref="Membership"/> entity (Task 20, implemented in Task 21). These tests define the
/// contract:
/// - Static factory <c>Membership.Create(TenantId tenantId, UserId userId, Role role)</c> creates
///   a new, <c>Active</c> membership linking a <c>User</c> to a <c>Tenant</c> with a <see cref="Role"/>.
/// - <c>Membership</c> implements <see cref="ITenantOwned"/> so it participates in the global
///   tenant query filter — <c>((ITenantOwned)membership).TenantId</c> equals the <c>TenantId</c>
///   passed to <c>Create</c>.
/// - Soft-removed (never hard-deleted) via <c>Status</c> (<see cref="MembershipStatus"/>) so
///   FR-025 can later report who lost access and when.
/// - Instance method <c>membership.Remove(IClock clock)</c> transitions <c>Status</c> to
///   <see cref="MembershipStatus.Removed"/> and records <c>clock.UtcNow</c> on
///   <c>RemovedAtUtc</c> (<see cref="DateTimeOffset"/>?, null while <c>Active</c>). The clock is
///   injected into the method (not pre-computed by the caller) so the entity itself, not the
///   caller, is responsible for reading "now" — consistent with <see cref="IClock"/>'s role as a
///   testable seam.
/// - Removing an already-<see cref="MembershipStatus.Removed"/> membership throws
///   <see cref="DomainException"/> — no double-removal.
/// - Public properties: <c>Id</c> (<see cref="MembershipId"/>), <c>TenantId</c>
///   (<see cref="TenantId"/>), <c>UserId</c> (<see cref="UserId"/>), <c>Role</c> (<see cref="Role"/>),
///   <c>Status</c> (<see cref="MembershipStatus"/>), <c>RemovedAtUtc</c> (<see cref="DateTimeOffset"/>?).
/// </summary>
public class MembershipTests
{
    private sealed class FakeClock(DateTimeOffset utcNow) : IClock
    {
        public DateTimeOffset UtcNow { get; } = utcNow;
    }

    [Fact]
    public void Create_WithValidArguments_SucceedsAndIsActiveWithNonDefaultId()
    {
        var tenantId = TenantId.New();
        var userId = UserId.New();

        var membership = Membership.Create(tenantId, userId, Role.Member);

        membership.Id.Should().NotBe(default(MembershipId));
        membership.TenantId.Should().Be(tenantId);
        membership.UserId.Should().Be(userId);
        membership.Role.Should().Be(Role.Member);
        membership.Status.Should().Be(MembershipStatus.Active);
        membership.RemovedAtUtc.Should().BeNull();
    }

    [Fact]
    public void Membership_ImplementsITenantOwned_ExposingTenantIdPassedToCreate()
    {
        var tenantId = TenantId.New();
        var userId = UserId.New();

        var membership = Membership.Create(tenantId, userId, Role.Reader);

        ((ITenantOwned)membership).TenantId.Should().Be(tenantId);
    }

    [Fact]
    public void Remove_WhenActive_TransitionsToRemovedAndRecordsRemovalTimestamp()
    {
        var membership = Membership.Create(TenantId.New(), UserId.New(), Role.Member);
        var removedAt = new DateTimeOffset(2026, 8, 11, 12, 0, 0, TimeSpan.Zero);
        var clock = new FakeClock(removedAt);

        membership.Remove(clock);

        membership.Status.Should().Be(MembershipStatus.Removed);
        membership.RemovedAtUtc.Should().Be(removedAt);
    }

    [Fact]
    public void Remove_WhenAlreadyRemoved_ThrowsDomainException()
    {
        var membership = Membership.Create(TenantId.New(), UserId.New(), Role.Member);
        var clock = new FakeClock(DateTimeOffset.UtcNow);
        membership.Remove(clock);

        Action act = () => membership.Remove(clock);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-017")]
    [Theory]
    [InlineData(Role.Member)]
    [InlineData(Role.Reader)]
    public void Create_WithGivenRole_ExposesThatRole(Role role)
    {
        var membership = Membership.Create(TenantId.New(), UserId.New(), role);

        membership.Role.Should().Be(role);
    }
}

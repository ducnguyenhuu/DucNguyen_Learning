using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;
using Xunit;

namespace Identity.UnitTests.Memberships;

/// <summary>
/// Failing (red) tests for the last-administrator invariant (FR-015), written as the target spec
/// for <see cref="TenantAdministration"/> (T074). <see cref="TenantAdministration"/> is currently
/// a minimal stub (T067) whose methods throw <see cref="NotImplementedException"/> — every test
/// here is therefore expected to fail at runtime with that exception until T074 implements the
/// real invariant.
/// </summary>
public class LastAdministratorTests
{
    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRemovalAllowed_SoleAdministrator_ThrowsDomainException()
    {
        var tenantId = TenantId.New();
        var soleAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var activeMemberships = new[] { soleAdministrator };

        var act = () => TenantAdministration.EnsureRemovalAllowed(activeMemberships, soleAdministrator);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRoleChangeAllowed_SoleAdministratorDemotedToMember_ThrowsDomainException()
    {
        var tenantId = TenantId.New();
        var soleAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var activeMemberships = new[] { soleAdministrator };

        var act = () => TenantAdministration.EnsureRoleChangeAllowed(
            activeMemberships, soleAdministrator, Role.Member);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRoleChangeAllowed_SoleAdministratorDemotedToReader_ThrowsDomainException()
    {
        var tenantId = TenantId.New();
        var soleAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var activeMemberships = new[] { soleAdministrator };

        var act = () => TenantAdministration.EnsureRoleChangeAllowed(
            activeMemberships, soleAdministrator, Role.Reader);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRemovalAllowed_TwoAdministrators_RemovingOneSucceeds()
    {
        var tenantId = TenantId.New();
        var firstAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var secondAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var activeMemberships = new[] { firstAdministrator, secondAdministrator };

        var act = () => TenantAdministration.EnsureRemovalAllowed(activeMemberships, firstAdministrator);

        act.Should().NotThrow();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRoleChangeAllowed_TwoAdministrators_DemotingOneSucceeds()
    {
        var tenantId = TenantId.New();
        var firstAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var secondAdministrator = Membership.Create(tenantId, UserId.New(), Role.Administrator);
        var activeMemberships = new[] { firstAdministrator, secondAdministrator };

        var act = () => TenantAdministration.EnsureRoleChangeAllowed(
            activeMemberships, firstAdministrator, Role.Member);

        act.Should().NotThrow();
    }
}

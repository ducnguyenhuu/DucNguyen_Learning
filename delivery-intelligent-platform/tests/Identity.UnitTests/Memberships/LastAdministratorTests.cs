using ArchitectureTests.Support;
using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Xunit;

namespace Identity.UnitTests.Memberships;

/// <summary>
/// Tests for the last-administrator invariant (FR-015), enforced by
/// <see cref="OrganizationAdministration"/>: the organization must always keep at least one active
/// administrator, so removing or demoting the sole administrator is refused, while removing or
/// demoting one of several administrators is allowed.
/// </summary>
public class LastAdministratorTests
{
    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRemovalAllowed_SoleAdministrator_ThrowsDomainException()
    {
        var soleAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var activeMemberships = new[] { soleAdministrator };

        var act = () => OrganizationAdministration.EnsureRemovalAllowed(activeMemberships, soleAdministrator);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRoleChangeAllowed_SoleAdministratorDemotedToMember_ThrowsDomainException()
    {
        var soleAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var activeMemberships = new[] { soleAdministrator };

        var act = () => OrganizationAdministration.EnsureRoleChangeAllowed(
            activeMemberships, soleAdministrator, Role.Member);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRoleChangeAllowed_SoleAdministratorDemotedToReader_ThrowsDomainException()
    {
        var soleAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var activeMemberships = new[] { soleAdministrator };

        var act = () => OrganizationAdministration.EnsureRoleChangeAllowed(
            activeMemberships, soleAdministrator, Role.Reader);

        act.Should().Throw<DomainException>();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRemovalAllowed_TwoAdministrators_RemovingOneSucceeds()
    {
        var firstAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var secondAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var activeMemberships = new[] { firstAdministrator, secondAdministrator };

        var act = () => OrganizationAdministration.EnsureRemovalAllowed(activeMemberships, firstAdministrator);

        act.Should().NotThrow();
    }

    [CoversRequirement("FR-015")]
    [Fact]
    public void EnsureRoleChangeAllowed_TwoAdministrators_DemotingOneSucceeds()
    {
        var firstAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var secondAdministrator = Membership.Create(UserId.New(), Role.Administrator);
        var activeMemberships = new[] { firstAdministrator, secondAdministrator };

        var act = () => OrganizationAdministration.EnsureRoleChangeAllowed(
            activeMemberships, firstAdministrator, Role.Member);

        act.Should().NotThrow();
    }
}

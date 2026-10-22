using ArchitectureTests.Support;
using AwesomeAssertions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Users;
using Xunit;

namespace Tenancy.UnitTests.Users;

/// <summary>
/// Failing (red) unit tests specifying the public API of the not-yet-implemented
/// <see cref="User"/> entity (Task 18, implemented in Task 19). These tests define the contract:
/// - Static factory <c>User.Create(Guid entraTenantId, Guid entraObjectId, EmailAddress email)</c>
///   creates a new <c>User</c>.
/// - <c>User</c>'s stable identity for lookup purposes is the composite
///   <c>(EntraTenantId, EntraObjectId)</c> — never <c>Email</c> (mutable, display-only, per
///   research.md R2) and never <c>oid</c>/<c>sub</c> alone.
/// - Public properties: <c>Id</c> (<see cref="UserId"/>), <c>EntraTenantId</c> (<see cref="Guid"/>),
///   <c>EntraObjectId</c> (<see cref="Guid"/>), <c>Email</c> (<see cref="EmailAddress"/>).
/// - <c>Email</c> validation is delegated entirely to <see cref="EmailAddress"/> — <c>User</c>
///   does not duplicate that validation.
/// </summary>
public class UserTests
{
    [Fact]
    public void Create_WithValidEntraIdentityAndEmail_SucceedsAndExposesAllProperties()
    {
        var entraTenantId = Guid.NewGuid();
        var entraObjectId = Guid.NewGuid();
        var email = new EmailAddress("alice@example.com");

        var user = User.Create(entraTenantId, entraObjectId, email);

        user.EntraTenantId.Should().Be(entraTenantId);
        user.EntraObjectId.Should().Be(entraObjectId);
        user.Email.Should().Be(email);
        user.Id.Should().NotBe(default(UserId));
    }

    [CoversRequirement("FR-003")]
    [Fact]
    public void Create_TwoUsersWithSameEntraIdentityButDifferentEmail_ExposeSameComparableEntraIdentity()
    {
        var entraTenantId = Guid.NewGuid();
        var entraObjectId = Guid.NewGuid();

        var first = User.Create(entraTenantId, entraObjectId, new EmailAddress("alice@example.com"));
        var second = User.Create(entraTenantId, entraObjectId, new EmailAddress("alice.alias@example.com"));

        // The composite (EntraTenantId, EntraObjectId) is the stable identity for lookup purposes —
        // callers such as T036's EnsureUserProvisioned key on these two directly comparable
        // properties, regardless of Email, which is display/invitation-matching only.
        first.EntraTenantId.Should().Be(second.EntraTenantId);
        first.EntraObjectId.Should().Be(second.EntraObjectId);
        first.Email.Should().NotBe(second.Email);
    }

    [Fact]
    public void Create_WithInvalidEmail_PropagatesDomainExceptionFromEmailAddress()
    {
        var entraTenantId = Guid.NewGuid();
        var entraObjectId = Guid.NewGuid();

        Action act = () => User.Create(entraTenantId, entraObjectId, new EmailAddress("not-an-email"));

        act.Should().Throw<DomainException>();
    }
}

using AwesomeAssertions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Tenants;
using Xunit;

namespace Tenancy.UnitTests.Tenants;

/// <summary>
/// Failing (red) unit tests specifying the public API of the not-yet-implemented
/// <see cref="Tenant"/> aggregate root (Task 17). These tests define the contract:
/// - Static factory <c>Tenant.Create(string displayName)</c> creates a new, <c>Active</c> tenant.
/// - Instance method <c>tenant.Rename(string newDisplayName)</c> validates and updates <c>DisplayName</c>.
/// - <c>DisplayName</c> is required (not null/empty/whitespace) but explicitly not unique.
/// - <c>Settings</c> is a non-null owned <c>TenantSettings</c> value present from creation.
/// - <c>Id</c> is a non-default <see cref="TenantId"/>.
/// </summary>
public class TenantTests
{
    [Fact]
    public void Create_WithValidDisplayName_SucceedsAndIsActive()
    {
        var tenant = Tenant.Create("Acme Corp");

        tenant.DisplayName.Should().Be("Acme Corp");
        tenant.Status.Should().Be(TenantStatus.Active);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Create_WithNullOrEmptyOrWhitespaceDisplayName_ThrowsDomainException(string? invalidName)
    {
        Action act = () => Tenant.Create(invalidName!);

        act.Should().Throw<DomainException>();
    }

    [Fact]
    public void Rename_WithValidNewName_UpdatesDisplayName()
    {
        var tenant = Tenant.Create("Acme Corp");

        tenant.Rename("Acme Corporation");

        tenant.DisplayName.Should().Be("Acme Corporation");
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Rename_WithNullOrEmptyOrWhitespaceName_ThrowsDomainExceptionAndLeavesNameUnchanged(string? invalidName)
    {
        var tenant = Tenant.Create("Acme Corp");

        Action act = () => tenant.Rename(invalidName!);

        act.Should().Throw<DomainException>();
        tenant.DisplayName.Should().Be("Acme Corp");
    }

    [Fact]
    public void Create_NewTenant_HasNonNullIdAndSettings()
    {
        var tenant = Tenant.Create("Acme Corp");

        tenant.Id.Should().NotBe(default(TenantId));
        tenant.Settings.Should().NotBeNull();
    }

    /// <summary>
    /// The domain must enforce the same upper bound the database column declares. Before
    /// ADR-021, <c>TenantConfiguration</c> set <c>HasMaxLength(200)</c> while
    /// <c>EnsureValidDisplayName</c> checked only null/whitespace — so an over-long name passed
    /// the domain, reached SQL Server, and surfaced as a <c>500</c> rather than a <c>400</c>.
    /// ADR-021 records that deferring a validation library does not excuse this gap.
    /// </summary>
    [Fact]
    public void Create_WithDisplayNameAtMaxLength_Succeeds()
    {
        var atLimit = new string('a', Tenant.DisplayNameMaxLength);

        var tenant = Tenant.Create(atLimit);

        tenant.DisplayName.Should().Be(atLimit);
    }

    [Fact]
    public void Create_WithDisplayNameExceedingMaxLength_ThrowsDomainException()
    {
        var overLimit = new string('a', Tenant.DisplayNameMaxLength + 1);

        Action act = () => Tenant.Create(overLimit);

        act.Should().Throw<DomainException>();
    }

    [Fact]
    public void Rename_WithDisplayNameExceedingMaxLength_ThrowsDomainExceptionAndLeavesNameUnchanged()
    {
        var tenant = Tenant.Create("Acme Corp");
        var overLimit = new string('a', Tenant.DisplayNameMaxLength + 1);

        Action act = () => tenant.Rename(overLimit);

        act.Should().Throw<DomainException>();
        tenant.DisplayName.Should().Be("Acme Corp");
    }
}

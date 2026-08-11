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
}

using AwesomeAssertions;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Tenants;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Memberships;
using Tenancy.Domain.Tenants;
using Xunit;

namespace Tenancy.UnitTests.Tenants;

/// <summary>
/// Unit tests for <see cref="GetTenant"/>, <see cref="RenameTenant"/>, and
/// <see cref="ListTenants"/> (T055), using hand-rolled in-memory fakes of
/// <see cref="ITenantRepository"/> and <see cref="IMembershipDirectory"/> — no real database is
/// needed to verify these use cases' own logic (get, get-then-mutate-then-save, and
/// get-memberships-then-get-many, respectively). Follows the same fake-repository pattern as
/// T054's <see cref="CreateTenantTests"/>.
/// </summary>
public class GetRenameListTenantsTests
{
    private sealed class FakeTenantRepository : ITenantRepository
    {
        public Tenant? CurrentTenant { get; set; }

        public IReadOnlyList<Tenant> TenantsById { get; set; } = [];

        public Tenant? SavedTenant { get; private set; }

        public int SaveCallCount { get; private set; }

        public IReadOnlyCollection<TenantId>? RequestedTenantIds { get; private set; }

        public Task<Tenant?> GetCurrentAsync(CancellationToken ct)
        {
            return Task.FromResult(CurrentTenant);
        }

        public Task<IReadOnlyList<Tenant>> GetManyByIdsAsync(IReadOnlyCollection<TenantId> tenantIds, CancellationToken ct)
        {
            RequestedTenantIds = tenantIds;
            return Task.FromResult(TenantsById);
        }

        public Task SaveAsync(Tenant tenant, CancellationToken ct)
        {
            SavedTenant = tenant;
            SaveCallCount++;
            return Task.CompletedTask;
        }
    }

    private sealed class FakeMembershipDirectory : IMembershipDirectory
    {
        public IReadOnlyList<Membership> Memberships { get; set; } = [];

        public Task<IReadOnlyList<Membership>> GetMembershipsForUserAsync(UserId userId, CancellationToken ct)
        {
            return Task.FromResult(Memberships);
        }
    }

    [Fact]
    public async Task GetTenant_ReturnsWhateverTheRepositoryProvides()
    {
        var fakeRepository = new FakeTenantRepository
        {
            CurrentTenant = Tenant.Create("Acme Corp"),
        };
        var useCase = new GetTenant(fakeRepository);

        var result = await useCase.ExecuteAsync(CancellationToken.None);

        result.Should().BeSameAs(fakeRepository.CurrentTenant);
    }

    [Fact]
    public async Task RenameTenant_WithInvalidDisplayName_ThrowsDomainException_AndNeverSaves()
    {
        var fakeRepository = new FakeTenantRepository
        {
            CurrentTenant = Tenant.Create("Acme Corp"),
        };
        var useCase = new RenameTenant(fakeRepository);

        var act = () => useCase.ExecuteAsync(" ", CancellationToken.None);

        await act.Should().ThrowAsync<DomainException>();
        fakeRepository.SaveCallCount.Should().Be(0);
        fakeRepository.SavedTenant.Should().BeNull();
    }

    [Fact]
    public async Task RenameTenant_WithValidDisplayName_RenamesAndSaves()
    {
        var tenant = Tenant.Create("Acme Corp");
        var fakeRepository = new FakeTenantRepository
        {
            CurrentTenant = tenant,
        };
        var useCase = new RenameTenant(fakeRepository);

        var result = await useCase.ExecuteAsync("Acme Corporation", CancellationToken.None);

        result.Should().BeSameAs(tenant);
        result!.DisplayName.Should().Be("Acme Corporation");
        fakeRepository.SaveCallCount.Should().Be(1);
        fakeRepository.SavedTenant.Should().BeSameAs(tenant);
    }

    [Fact]
    public async Task ListTenants_WithNoMemberships_ReturnsEmptyList()
    {
        var fakeMembershipDirectory = new FakeMembershipDirectory
        {
            Memberships = [],
        };
        var fakeRepository = new FakeTenantRepository();
        var useCase = new ListTenants(fakeMembershipDirectory, fakeRepository);

        var result = await useCase.ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Should().BeEmpty();
        fakeRepository.RequestedTenantIds.Should().BeNull();
    }

    [Fact]
    public async Task ListTenants_CallsGetManyByIdsAsync_WithDistinctTenantIdsFromMemberships()
    {
        var userId = UserId.New();
        var tenantOne = TenantId.New();
        var tenantTwo = TenantId.New();
        var fakeMembershipDirectory = new FakeMembershipDirectory
        {
            Memberships =
            [
                Membership.Create(tenantOne, userId, Role.Administrator),
                Membership.Create(tenantTwo, userId, Role.Member),
                Membership.Create(tenantOne, userId, Role.Member),
            ],
        };
        var expectedTenants = new List<Tenant> { Tenant.Create("Acme Corp"), Tenant.Create("Globex") };
        var fakeRepository = new FakeTenantRepository
        {
            TenantsById = expectedTenants,
        };
        var useCase = new ListTenants(fakeMembershipDirectory, fakeRepository);

        var result = await useCase.ExecuteAsync(userId, CancellationToken.None);

        result.Should().BeSameAs(expectedTenants);
        fakeRepository.RequestedTenantIds.Should().NotBeNull();
        fakeRepository.RequestedTenantIds!.Should().HaveCount(2);
        fakeRepository.RequestedTenantIds.Should().BeEquivalentTo([tenantOne, tenantTwo]);
    }
}

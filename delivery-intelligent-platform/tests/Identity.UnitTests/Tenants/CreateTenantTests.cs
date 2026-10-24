using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Tenants;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Domain.Tenants;
using Xunit;

namespace Identity.UnitTests.Tenants;

/// <summary>
/// Unit tests for <see cref="CreateTenant"/> (T054), using a hand-rolled in-memory fake of
/// <see cref="ICreateTenantRepository"/> — no real database is needed to verify this use case's
/// own logic (calling <c>Tenant.Create</c>/<c>Membership.Create</c> in the right order and
/// handing both to the port in one call). Whether the persistence layer actually saves both in
/// one transaction and stamps <c>TenantId</c> correctly is a Infrastructure-level concern,
/// verified later against a real database via T058's endpoint tests, not here.
/// </summary>
public class CreateTenantTests
{
    private sealed class FakeCreateTenantRepository : ICreateTenantRepository
    {
        public Tenant? SavedTenant { get; private set; }

        public Membership? SavedMembership { get; private set; }

        public Task AddAsync(Tenant tenant, Membership administratorMembership, CancellationToken ct)
        {
            SavedTenant = tenant;
            SavedMembership = administratorMembership;
            return Task.CompletedTask;
        }
    }

    [CoversRequirement("FR-005")]
    [Fact]
    public async Task ExecuteAsync_CreatesTenantAndAdministratorMembership_InOneCall()
    {
        var fakeRepository = new FakeCreateTenantRepository();
        var useCase = new CreateTenant(fakeRepository, NullLogger<CreateTenant>.Instance);
        var creatorUserId = UserId.New();

        var tenant = await useCase.ExecuteAsync("Acme Corp", creatorUserId, CancellationToken.None);

        tenant.DisplayName.Should().Be("Acme Corp");

        fakeRepository.SavedTenant.Should().BeSameAs(tenant);
        fakeRepository.SavedMembership.Should().NotBeNull();
        fakeRepository.SavedMembership!.TenantId.Should().Be(tenant.Id);
        fakeRepository.SavedMembership!.UserId.Should().Be(creatorUserId);
        fakeRepository.SavedMembership!.Role.Should().Be(Role.Administrator);
    }

    [Fact]
    public async Task ExecuteAsync_WithInvalidDisplayName_ThrowsDomainException_AndNeverCallsRepository()
    {
        var fakeRepository = new FakeCreateTenantRepository();
        var useCase = new CreateTenant(fakeRepository, NullLogger<CreateTenant>.Instance);

        var act = () => useCase.ExecuteAsync(" ", UserId.New(), CancellationToken.None);

        await act.Should().ThrowAsync<DomainException>();
        fakeRepository.SavedTenant.Should().BeNull();
    }
}

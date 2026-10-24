using AwesomeAssertions;
using Microsoft.Extensions.DependencyInjection;
using Identity.Domain.Abstractions;
using Identity.Domain.Memberships;
using Identity.Infrastructure.Persistence;
using Identity.IntegrationTests.Infrastructure;
using Xunit;

namespace Identity.IntegrationTests.Scenarios;

/// <summary>
/// Defence in depth for ADR-013's tenant-scoping mechanism: writing an <see cref="ITenantOwned"/>
/// entity while <see cref="IdentityDbContext.CurrentTenantId"/> has never been set must be refused,
/// not silently stamped with <c>Guid.Empty</c>.
/// </summary>
/// <remarks>
/// <para>
/// <b>Why this is a real gap and not a theoretical one.</b> Spec 002's checklist review
/// (CHK023-CHK026) established that S3's structural gate on background jobs — FR-012, which
/// forbids a job from taking a persistence dependency in its constructor — cannot close the
/// property U12 actually cares about. A <see cref="Microsoft.Extensions.Hosting.BackgroundService"/>
/// is a singleton and must resolve scoped services through <c>IServiceScopeFactory</c> at runtime,
/// so constructor inspection is blind to it by construction. No structural gate can see that.
/// </para>
/// <para>
/// <b>What was verified about the current behaviour, rather than assumed.</b>
/// <see cref="IdentityDbContext.CurrentTenantId"/> is a non-nullable <see cref="TenantId"/> struct,
/// so "unset" means <c>default</c>, i.e. <c>Guid.Empty</c> — never <c>null</c>. Against that value:
/// <list type="bullet">
/// <item><b>Reads</b> fail closed. The <c>"TenantFilter"</c> global query filter becomes
/// <c>TenantId == Guid.Empty</c>, which matches no real row.</item>
/// <item><b>Update and delete</b> of an existing row fail closed. <c>TenantSaveChangesInterceptor</c>
/// throws because the entity's original <c>TenantId</c> differs from the ambient one.</item>
/// <item><b>Insert</b> did <i>not</i> fail closed. The interceptor unconditionally stamped the
/// ambient value, producing a row owned by <c>Guid.Empty</c> — a tenant that does not exist.</item>
/// </list>
/// That third case is the only genuine hole, and it is what this test closes. Note this is a
/// silent-orphan defect rather than a cross-tenant leak: U12's framing of the background-job gap as
/// "the most plausible route to a cross-tenant leak" overstates it against this implementation,
/// which is recorded in spec 002 rather than left to the next reader to rediscover.
/// </para>
/// <para>
/// <b>Why the guard cannot break the two unscoped write flows.</b> Both operations that insert a
/// tenant-owned entity without an ambient request tenant already set the context explicitly first —
/// <c>CreateTenantRepository.AddAsync</c> (<c>CurrentTenantId = tenant.Id</c>, whose own doc comment
/// explains that omitting it would mis-stamp the membership) and
/// <c>InvitationRepository.AddMembershipForAcceptanceAsync</c>
/// (<c>CurrentTenantId = invitation.TenantId</c>). The guard therefore only fires on a genuine
/// defect, and it converts a rule those two comments state into one the runtime enforces
/// (Constitution Principle VII).
/// </para>
/// </remarks>
public class UnsetTenantContextWriteTests : IdentityIntegrationTestBase
{
    public UnsetTenantContextWriteTests(SqlServerFixture sqlServerFixture, ApiFactory factory)
        : base(sqlServerFixture, factory)
    {
    }

    [Fact]
    public async Task Insert_TenantOwnedEntity_WithUnsetTenantContext_IsRefused()
    {
        using var scope = Factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        // Deliberately do NOT set dbContext.CurrentTenantId — this is the background-job-style
        // mistake FR-012's structural gate cannot see.
        dbContext.CurrentTenantId.Should().Be(
            default(TenantId),
            "the scenario under test is an ambient tenant that was never resolved");

        var membership = Membership.Create(
            TenantId.New(),
            UserId.New(),
            Role.Administrator);

        dbContext.Memberships.Add(membership);

        var act = async () => await dbContext.SaveChangesAsync();

        await act.Should().ThrowAsync<DomainException>(
            "inserting a tenant-owned entity with no ambient tenant would create a row owned by " +
            "Guid.Empty — a tenant that does not exist");
    }

    [Fact]
    public async Task Insert_TenantOwnedEntity_WithTenantContextSet_Succeeds()
    {
        // The guard must refuse only the unset case. This is the regression half: the two real
        // unscoped flows (create-tenant, accept-invitation) both set the context before saving,
        // and they must keep working.
        var seed = await Factory.SeedTwoTenantsAsync();

        using var scope = Factory.Services.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<IdentityDbContext>();

        dbContext.CurrentTenantId = seed.TenantA.TenantId;

        var membership = Membership.Create(
            seed.TenantA.TenantId,
            UserId.New(),
            Role.Member);

        dbContext.Memberships.Add(membership);

        var act = async () => await dbContext.SaveChangesAsync();

        await act.Should().NotThrowAsync(
            "an explicitly scoped insert is the sanctioned path and must remain unaffected");
    }
}

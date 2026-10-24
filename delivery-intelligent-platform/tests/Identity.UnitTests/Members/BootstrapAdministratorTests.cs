using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.Extensions.Logging.Abstractions;
using Identity.Application.Abstractions;
using Identity.Application.Members;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Identity.Domain.Memberships;
using Xunit;

namespace Identity.UnitTests.Members;

/// <summary>
/// Unit tests for <see cref="BootstrapAdministrator"/> (ADR-025: the first authenticated user
/// becomes the organization's first administrator — FR-005 as reinterpreted), using hand-rolled
/// in-memory fakes following <c>RemoveMemberTests</c>' convention.
/// </summary>
/// <remarks>
/// Whether <see cref="IMembershipRepository.TryAddFirstAdministratorAsync"/> really serializes two
/// racing first sign-ins is a persistence concern (an application lock against a real database),
/// proven by integration tests, not here. These tests pin the use case's own logic: what it hands
/// the repository, what it stages for audit, and how it reports the repository's answer.
/// </remarks>
public class BootstrapAdministratorTests
{
    private sealed class FakeMembershipRepository : IMembershipRepository
    {
        public bool OrganizationHasNoMembers { get; init; } = true;

        public Membership? OfferedMembership { get; private set; }

        public Task<IReadOnlyList<Membership>> GetActiveMembersAsync(CancellationToken ct) =>
            throw new NotSupportedException("Not used by BootstrapAdministratorTests.");

        public Task<Membership?> GetActiveMembershipForUserAsync(UserId userId, CancellationToken ct) =>
            throw new NotSupportedException("Not used by BootstrapAdministratorTests.");

        public Task RemoveMembershipAsync(MembershipId membershipId, CancellationToken ct) =>
            throw new NotSupportedException("Not used by BootstrapAdministratorTests.");

        public Task<bool> TryAddFirstAdministratorAsync(Membership administratorMembership, CancellationToken ct)
        {
            OfferedMembership = administratorMembership;
            return Task.FromResult(OrganizationHasNoMembers);
        }

        public Task SaveAsync(Membership membership, CancellationToken ct) =>
            throw new NotSupportedException("Not used by BootstrapAdministratorTests.");
    }

    private sealed class FakeAuditWriter : IAuditWriter
    {
        public List<AuditEntry> RecordedEntries { get; } = [];

        public Task RecordAsync(AuditEntry entry, CancellationToken ct)
        {
            RecordedEntries.Add(entry);
            return Task.CompletedTask;
        }

        public Task RecordAndSaveAsync(AuditEntry entry, CancellationToken ct) =>
            throw new NotSupportedException("Not used by this test suite; only RecordAsync is exercised.");
    }

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow => new(2026, 1, 1, 0, 0, 0, TimeSpan.Zero);
    }

    private static BootstrapAdministrator CreateUseCase(
        FakeMembershipRepository repository, FakeAuditWriter auditWriter) =>
        new(repository, auditWriter, new FakeClock(), NullLogger<BootstrapAdministrator>.Instance);

    [CoversRequirement("FR-005")]
    [Fact]
    public async Task ExecuteAsync_EmptyOrganization_ReturnsAdministratorMembership_AndStagesAudit()
    {
        var repository = new FakeMembershipRepository { OrganizationHasNoMembers = true };
        var auditWriter = new FakeAuditWriter();
        var callerUserId = UserId.New();

        var result = await CreateUseCase(repository, auditWriter).ExecuteAsync(callerUserId, CancellationToken.None);

        result.Kind.Should().Be(BootstrapAdministratorResultKind.Success);
        result.Membership.Should().NotBeNull();
        result.Membership.Should().BeSameAs(repository.OfferedMembership);
        result.Membership!.UserId.Should().Be(callerUserId);
        result.Membership.Role.Should().Be(Role.Administrator);
        result.Membership.Status.Should().Be(MembershipStatus.Active);

        auditWriter.RecordedEntries.Should().ContainSingle();
        var entry = auditWriter.RecordedEntries[0];
        entry.Action.Should().Be("membership.bootstrapped");
        entry.ActorUserId.Should().Be(callerUserId);
    }

    /// <summary>
    /// Once anyone is a member, new members join only by invitation. The audit entry is still
    /// staged before the repository is asked (so a successful save flushes both together), but
    /// the repository returns <c>false</c> without saving, so on this path nothing is written —
    /// see <see cref="BootstrapAdministrator"/>'s remarks.
    /// </summary>
    [CoversRequirement("FR-005")]
    [Fact]
    public async Task ExecuteAsync_OrganizationAlreadyHasMembers_ReturnsConflict()
    {
        var repository = new FakeMembershipRepository { OrganizationHasNoMembers = false };
        var auditWriter = new FakeAuditWriter();

        var result = await CreateUseCase(repository, auditWriter).ExecuteAsync(UserId.New(), CancellationToken.None);

        result.Kind.Should().Be(BootstrapAdministratorResultKind.Conflict);
        result.Membership.Should().BeNull();
    }
}

using ArchitectureTests.Support;
using AwesomeAssertions;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Tenancy.Api.Authorization;
using Tenancy.Application.Abstractions;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Auditing;
using Tenancy.Domain.Users;
using Xunit;

namespace Tenancy.UnitTests.Authorization;

/// <summary>
/// Unit tests for <see cref="AdministratorOnlyAuthorizationHandler"/>, using ASP.NET
/// Core's own test-friendly <see cref="AuthorizationHandlerContext"/> construction directly — no
/// full HTTP pipeline needed — with a hand-rolled fake <see cref="ITenantContext"/> following
/// <c>RemoveMemberTests</c>' established convention.
/// </summary>
public class AdministratorOnlyAuthorizationHandlerTests
{
    private static readonly TenantId TestTenantId = new(Guid.CreateVersion7());

    private sealed class FakeTenantContext : ITenantContext
    {
        public TenantId TenantId => TestTenantId;

        public Role Role { get; init; }
    }

    /// <summary>
    /// Fake standing in for "the tenant context was never resolved" — mirrors
    /// <c>HttpContextTenantContext</c>'s documented contract (see <see cref="ITenantContext"/>'s
    /// remarks) that both properties must throw, never return a default value, if accessed
    /// before <c>TenantContextResolutionMiddleware</c> has populated them.
    /// </summary>
    private sealed class UnresolvedTenantContext : ITenantContext
    {
        public TenantId TenantId => throw new InvalidOperationException("Tenant context has not been resolved.");

        public Role Role => throw new InvalidOperationException("Tenant context has not been resolved.");
    }

    /// <summary>
    /// Minimal capturing fake for <see cref="ILogger{TCategoryName}"/> — following this test
    /// file's own established pattern of hand-rolled fakes over a mocking library — used to prove
    /// the FR-025 authorization-refusal log call actually fires with templated arguments, not
    /// string interpolation.
    /// </summary>
    private sealed class CapturingLogger : ILogger<AdministratorOnlyAuthorizationHandler>
    {
        public List<string> Messages { get; } = [];

        public IDisposable? BeginScope<TState>(TState state) where TState : notnull => null;

        public bool IsEnabled(LogLevel logLevel) => true;

        public void Log<TState>(
            LogLevel logLevel,
            EventId eventId,
            TState state,
            Exception? exception,
            Func<TState, Exception?, string> formatter)
        {
            Messages.Add(formatter(state, exception));
        }
    }

    /// <summary>
    /// Minimal fake standing in for the real EF-Core-backed <see cref="IUserRepository"/> — this
    /// handler only ever needs <see cref="FindByEntraIdentityAsync"/> to resolve the refused
    /// caller's internal <see cref="UserId"/> for the audit entry it stages.
    /// </summary>
    private sealed class FakeUserRepository : IUserRepository
    {
        public User? UserToReturn { get; init; }

        public Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct) =>
            Task.FromResult(UserToReturn);

        public Task AddAsync(User user, CancellationToken ct) => throw new NotImplementedException();

        public Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct) =>
            throw new NotImplementedException();
    }

    /// <summary>
    /// Capturing fake for <see cref="IAuditWriter"/> — records every <see cref="AuditEntry"/>
    /// passed to <see cref="RecordAndSaveAsync"/> (the method this handler uses, since a refusal
    /// has no later use-case save to piggyback on) and optionally throws to prove this handler
    /// lets a failed audit write propagate rather than swallowing it.
    /// </summary>
    private sealed class FakeAuditWriter : IAuditWriter
    {
        public List<AuditEntry> RecordedAndSaved { get; } = [];

        public Exception? ThrowOnSave { get; init; }

        public Task RecordAsync(AuditEntry entry, CancellationToken ct) => throw new NotImplementedException();

        public Task RecordAndSaveAsync(AuditEntry entry, CancellationToken ct)
        {
            if (ThrowOnSave is not null)
            {
                throw ThrowOnSave;
            }

            RecordedAndSaved.Add(entry);
            return Task.CompletedTask;
        }
    }

    private sealed class FakeClock : IClock
    {
        public DateTimeOffset UtcNow { get; init; } = DateTimeOffset.UtcNow;
    }

    private static async Task<(AuthorizationHandlerContext Context, FakeAuditWriter AuditWriter)> EvaluateAsync(
        ITenantContext tenantContext,
        ILogger<AdministratorOnlyAuthorizationHandler>? logger = null,
        IUserRepository? userRepository = null,
        FakeAuditWriter? auditWriter = null,
        System.Security.Claims.ClaimsPrincipal? user = null)
    {
        var writer = auditWriter ?? new FakeAuditWriter();
        var handler = new AdministratorOnlyAuthorizationHandler(
            tenantContext,
            userRepository ?? new FakeUserRepository(),
            writer,
            new FakeClock(),
            logger ?? NullLogger<AdministratorOnlyAuthorizationHandler>.Instance);
        var requirement = new AdministratorOnlyRequirement();
        var context = new AuthorizationHandlerContext(
            [requirement],
            user ?? new System.Security.Claims.ClaimsPrincipal(),
            resource: null);

        await handler.HandleAsync(context);
        return (context, writer);
    }

    [CoversRequirement("FR-018")]
    [CoversRequirement("FR-019")]
    [Fact]
    public async Task HandleRequirementAsync_AdministratorRole_Succeeds()
    {
        var (context, _) = await EvaluateAsync(new FakeTenantContext { Role = Role.Administrator });

        context.HasSucceeded.Should().BeTrue();
    }

    [CoversRequirement("FR-017")]
    [CoversRequirement("FR-018")]
    [CoversRequirement("FR-019")]
    [Theory]
    [InlineData(Role.Member)]
    [InlineData(Role.Reader)]
    public async Task HandleRequirementAsync_NonAdministratorRole_Fails(Role role)
    {
        var (context, _) = await EvaluateAsync(new FakeTenantContext { Role = role });

        context.HasSucceeded.Should().BeFalse();
    }

    /// <summary>
    /// FR-025 gap closure: a role-based refusal must produce a structured log entry — tenant id,
    /// required role, and actual role — via a templated <c>LogWarning</c> call, not string
    /// interpolation. Mirrors <c>TenantContextResolutionMiddleware</c>'s established
    /// logging convention for the earlier "not a member at all" refusal path.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task HandleRequirementAsync_NonAdministratorRole_LogsAuthorizationRefusal()
    {
        var logger = new CapturingLogger();

        var (context, _) = await EvaluateAsync(new FakeTenantContext { Role = Role.Member }, logger);

        context.HasSucceeded.Should().BeFalse();
        logger.Messages.Should().ContainSingle(
            message => message.Contains("Authorization refused", StringComparison.Ordinal)
                && message.Contains(TestTenantId.Value.ToString(), StringComparison.OrdinalIgnoreCase)
                && message.Contains(nameof(Role.Administrator), StringComparison.Ordinal)
                && message.Contains(nameof(Role.Member), StringComparison.Ordinal));
    }

    /// <summary>
    /// Guards against a regression where the success path starts logging too — an authorization
    /// grant is not a refusal, and FR-025's refusal-logging requirement should not fire here.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task HandleRequirementAsync_AdministratorRole_DoesNotLogRefusal()
    {
        var logger = new CapturingLogger();

        await EvaluateAsync(new FakeTenantContext { Role = Role.Administrator }, logger);

        logger.Messages.Should().BeEmpty();
    }

    [Fact]
    public async Task HandleRequirementAsync_UnresolvedTenantContext_PropagatesException()
    {
        // Documents a deliberate design decision: this handler does not guard against an
        // unresolved ITenantContext. ASP.NET Core's own pipeline ordering does not guarantee
        // TenantContextResolutionMiddleware (an IEndpointFilter, running as part of endpoint
        // invocation) has already run by the time a policy using this handler is evaluated by
        // AuthorizationMiddleware (registered earlier, via UseAuthorization()). Letting the
        // exception propagate here turns a broken precondition into a fail-closed 500 (via
        // ProblemDetailsHandler) rather than silently succeeding or failing open.
        var act = () => EvaluateAsync(new UnresolvedTenantContext());

        await act.Should().ThrowAsync<InvalidOperationException>();
    }

    /// <summary>
    /// A role-based refusal must also stage-and-save an <see cref="AuditEntry"/> — via
    /// <see cref="IAuditWriter.RecordAndSaveAsync"/>, not <see cref="IAuditWriter.RecordAsync"/>,
    /// since a refusal short-circuits the request before any later use-case save would ever run.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task HandleRequirementAsync_NonAdministratorRole_RecordsAndSavesAuditEntry()
    {
        var entraTenantId = Guid.CreateVersion7();
        var entraObjectId = Guid.CreateVersion7();
        var user = User.Create(entraTenantId, entraObjectId, new EmailAddress("refused@example.com"));
        var claims = new System.Security.Claims.ClaimsPrincipal(
            new System.Security.Claims.ClaimsIdentity(
            [
                new System.Security.Claims.Claim("tid", entraTenantId.ToString()),
                new System.Security.Claims.Claim("oid", entraObjectId.ToString()),
            ]));

        var (context, auditWriter) = await EvaluateAsync(
            new FakeTenantContext { Role = Role.Member },
            userRepository: new FakeUserRepository { UserToReturn = user },
            user: claims);

        context.HasSucceeded.Should().BeFalse();
        auditWriter.RecordedAndSaved.Should().ContainSingle();
        var entry = auditWriter.RecordedAndSaved[0];
        entry.Action.Should().Be("authorization.refused");
        entry.TenantId.Should().Be(TestTenantId);
        entry.ActorUserId.Should().Be(user.Id);
    }

    /// <summary>
    /// The oid/tid claims are absent (or unresolvable to a provisioned user) in some refusal
    /// scenarios per the spec's edge case wording; this handler must tolerate that with a null
    /// <see cref="AuditEntry.ActorUserId"/> rather than throw.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task HandleRequirementAsync_NonAdministratorRole_NoOidClaim_RecordsAuditEntryWithNullActor()
    {
        var (_, auditWriter) = await EvaluateAsync(new FakeTenantContext { Role = Role.Member });

        auditWriter.RecordedAndSaved.Should().ContainSingle();
        auditWriter.RecordedAndSaved[0].ActorUserId.Should().BeNull();
    }

    /// <summary>
    /// Spec edge case: "the action must not be treated as complete if the audit write fails" —
    /// here, the "action" is the refusal itself. A failed audit save must propagate rather than
    /// be swallowed, so the caller never observes a 403 as if the audit trail had succeeded.
    /// </summary>
    [CoversRequirement("FR-025")]
    [Fact]
    public async Task HandleRequirementAsync_NonAdministratorRole_AuditWriteFails_PropagatesException()
    {
        var failingWriter = new FakeAuditWriter { ThrowOnSave = new InvalidOperationException("audit store unavailable") };

        var act = () => EvaluateAsync(new FakeTenantContext { Role = Role.Member }, auditWriter: failingWriter);

        await act.Should().ThrowAsync<InvalidOperationException>();
    }
}

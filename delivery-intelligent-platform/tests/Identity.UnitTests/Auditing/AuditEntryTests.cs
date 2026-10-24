using AwesomeAssertions;
using Identity.Domain.Abstractions;
using Identity.Domain.Auditing;
using Xunit;

namespace Identity.UnitTests.Auditing;

/// <summary>
/// Failing (red) unit tests specifying the public API of the not-yet-implemented
/// <see cref="AuditEntry"/> entity. These tests define the contract:
/// - Static factory <c>AuditEntry.Create(UserId? actorUserId, string action,
///   string resourceType, string resourceId, IClock clock)</c> creates a new audit entry with
///   <c>OccurredAtUtc</c> read from <paramref name="clock"/>'s current time — never
///   <c>DateTimeOffset.UtcNow</c> directly.
/// - <c>ActorUserId</c> may be <c>null</c> — this is the unauthenticated-refusal case, not an
///   error.
/// - <c>Action</c>, <c>ResourceType</c>, and <c>ResourceId</c> are required and throw
///   <see cref="DomainException"/> when null/empty/whitespace.
/// </summary>
public class AuditEntryTests
{
    private sealed class FakeClock(DateTimeOffset utcNow) : IClock
    {
        public DateTimeOffset UtcNow { get; } = utcNow;
    }

    [Fact]
    public void Create_WithValidArgumentsAndActor_SucceedsAndSetsOccurredAtFromClock()
    {
        var actorUserId = UserId.New();
        var occurredAt = new DateTimeOffset(2026, 8, 19, 9, 30, 0, TimeSpan.Zero);
        var clock = new FakeClock(occurredAt);

        var entry = AuditEntry.Create(
            actorUserId,
            "membership.removed",
            "Membership",
            "some-resource-id",
            clock);

        entry.Id.Should().NotBe(default(AuditEntryId));
        entry.ActorUserId.Should().Be(actorUserId);
        entry.Action.Should().Be("membership.removed");
        entry.ResourceType.Should().Be("Membership");
        entry.ResourceId.Should().Be("some-resource-id");
        entry.OccurredAtUtc.Should().Be(occurredAt);
    }

    [Fact]
    public void Create_WithNullActor_Succeeds()
    {
        var clock = new FakeClock(DateTimeOffset.UtcNow);

        var entry = AuditEntry.Create(
            actorUserId: null,
            "auth.refused",
            "Session",
            "unknown",
            clock);

        entry.ActorUserId.Should().BeNull();
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Create_WithEmptyAction_ThrowsDomainException(string? action)
    {
        var clock = new FakeClock(DateTimeOffset.UtcNow);

        Action act = () => AuditEntry.Create(
            UserId.New(),
            action!,
            "Membership",
            "some-resource-id",
            clock);

        act.Should().Throw<DomainException>();
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Create_WithEmptyResourceType_ThrowsDomainException(string? resourceType)
    {
        var clock = new FakeClock(DateTimeOffset.UtcNow);

        Action act = () => AuditEntry.Create(
            UserId.New(),
            "membership.removed",
            resourceType!,
            "some-resource-id",
            clock);

        act.Should().Throw<DomainException>();
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Create_WithEmptyResourceId_ThrowsDomainException(string? resourceId)
    {
        var clock = new FakeClock(DateTimeOffset.UtcNow);

        Action act = () => AuditEntry.Create(
            UserId.New(),
            "membership.removed",
            "Membership",
            resourceId!,
            clock);

        act.Should().Throw<DomainException>();
    }
}

using AwesomeAssertions;
using Microsoft.EntityFrameworkCore;
using Tenancy.Application.Abstractions;
using Tenancy.Application.Users;
using Tenancy.Domain.Abstractions;
using Tenancy.Domain.Users;
using Xunit;

namespace Tenancy.UnitTests.Users;

/// <summary>
/// Unit tests for <see cref="EnsureUserProvisioned"/>, using a hand-rolled in-memory fake of
/// <see cref="IUserRepository"/> — following <c>InviteMemberTests</c>' established convention.
/// These tests exist to lock down the get-or-create race handling (catch a <see cref="DbUpdateException"/>
/// from a losing insert, re-query, and return the winner's row) before that logic is refactored to
/// translate the caught exception into an Application-owned type. They must pass against the
/// current implementation unmodified.
/// </summary>
public class EnsureUserProvisionedTests
{
    private static readonly Guid TestEntraTenantId = Guid.CreateVersion7();
    private static readonly Guid TestEntraObjectId = Guid.CreateVersion7();
    private static readonly EmailAddress TestEmail = new("provisioned@example.com");

    private sealed class FakeUserRepository : IUserRepository
    {
        /// <summary>The user returned by <see cref="FindByEntraIdentityAsync"/>. Settable so a test
        /// can change this between the initial lookup and a post-race re-query.</summary>
        public User? UserToFind { get; set; }

        /// <summary>When set, <see cref="AddAsync"/> throws this once, then clears itself — used
        /// to simulate losing the insert race against a concurrent provisioning request.</summary>
        public DbUpdateException? ThrowOnAdd { get; set; }

        public User? AddedUser { get; private set; }

        public int FindByEntraIdentityCallCount { get; private set; }

        public Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct)
        {
            FindByEntraIdentityCallCount++;
            return Task.FromResult(UserToFind);
        }

        public Task AddAsync(User user, CancellationToken ct)
        {
            if (ThrowOnAdd is { } exception)
            {
                ThrowOnAdd = null;
                throw exception;
            }

            AddedUser = user;
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct) =>
            throw new NotSupportedException("Not used by EnsureUserProvisionedTests.");
    }

    [Fact]
    public async Task ExecuteAsync_NoExistingUser_CreatesAndReturnsNewUser()
    {
        var repository = new FakeUserRepository { UserToFind = null };
        var useCase = new EnsureUserProvisioned(repository);

        var result = await useCase.ExecuteAsync(TestEntraTenantId, TestEntraObjectId, TestEmail, CancellationToken.None);

        result.Should().BeSameAs(repository.AddedUser);
        result.EntraTenantId.Should().Be(TestEntraTenantId);
        result.EntraObjectId.Should().Be(TestEntraObjectId);
        result.Email.Should().Be(TestEmail);
    }

    [Fact]
    public async Task ExecuteAsync_ExistingUserFound_ReturnsExistingWithoutCreating()
    {
        var existingUser = User.Create(TestEntraTenantId, TestEntraObjectId, TestEmail);
        var repository = new FakeUserRepository { UserToFind = existingUser };
        var useCase = new EnsureUserProvisioned(repository);

        var result = await useCase.ExecuteAsync(TestEntraTenantId, TestEntraObjectId, TestEmail, CancellationToken.None);

        result.Should().BeSameAs(existingUser);
        repository.AddedUser.Should().BeNull();
    }

    [Fact]
    public async Task ExecuteAsync_LosesCreateRace_ReturnsRaceWinnerInsteadOfThrowing()
    {
        var raceWinner = User.Create(TestEntraTenantId, TestEntraObjectId, TestEmail);
        var repository = new FakeUserRepository
        {
            // Initial lookup finds nothing; AddAsync then loses the insert race. UserToFind is
            // flipped to the race winner's row so the subsequent re-query (triggered by the
            // caught DbUpdateException) finds the row the other request just inserted.
            UserToFind = null,
            ThrowOnAdd = new DbUpdateException("simulated unique-constraint violation"),
        };

        // Simulate the other request's insert completing between this call's two lookups.
        var useCase = new EnsureUserProvisioned(new RaceSimulatingUserRepository(repository, raceWinner));

        var result = await useCase.ExecuteAsync(TestEntraTenantId, TestEntraObjectId, TestEmail, CancellationToken.None);

        result.Should().BeSameAs(raceWinner);
    }

    [Fact]
    public async Task ExecuteAsync_AddThrowsAndRequeryFindsNothing_RethrowsOriginalException()
    {
        var thrownException = new DbUpdateException("simulated non-race DB error");
        var repository = new FakeUserRepository
        {
            // Initial lookup and the post-catch re-query both find nothing: the DbUpdateException
            // was not caused by the get-or-create race, so it must propagate unchanged.
            UserToFind = null,
            ThrowOnAdd = thrownException,
        };
        var useCase = new EnsureUserProvisioned(repository);

        var act = () => useCase.ExecuteAsync(TestEntraTenantId, TestEntraObjectId, TestEmail, CancellationToken.None);

        var thrown = await act.Should().ThrowAsync<DbUpdateException>();
        thrown.Which.Should().BeSameAs(thrownException);
    }

    /// <summary>
    /// Wraps <see cref="FakeUserRepository"/> so the *second* call to
    /// <see cref="IUserRepository.FindByEntraIdentityAsync"/> (the post-race re-query) returns the
    /// race winner, while the first call (the initial not-found check) still returns null — without
    /// needing a mocking library to express "different result on different calls".
    /// </summary>
    private sealed class RaceSimulatingUserRepository : IUserRepository
    {
        private readonly FakeUserRepository _inner;
        private readonly User _raceWinner;

        public RaceSimulatingUserRepository(FakeUserRepository inner, User raceWinner)
        {
            _inner = inner;
            _raceWinner = raceWinner;
        }

        public async Task<User?> FindByEntraIdentityAsync(Guid entraTenantId, Guid entraObjectId, CancellationToken ct)
        {
            var result = await _inner.FindByEntraIdentityAsync(entraTenantId, entraObjectId, ct);
            if (_inner.FindByEntraIdentityCallCount > 1)
            {
                return _raceWinner;
            }

            return result;
        }

        public Task AddAsync(User user, CancellationToken ct) => _inner.AddAsync(user, ct);

        public Task<IReadOnlyList<User>> FindByIdsAsync(IReadOnlyCollection<UserId> userIds, CancellationToken ct) =>
            _inner.FindByIdsAsync(userIds, ct);
    }
}

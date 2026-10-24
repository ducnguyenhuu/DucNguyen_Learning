# Architecture Tests

This project contains architecture-enforcement gates that validate layering, dependency boundaries, and other structural constraints across the Identity service.

## Scope

The following subdirectories are intentionally absent from this project:

- **ContractTests/** — Contract verification gates are planned for inclusion in slice S9 (Consumer-Contract Testing). Until those gates are implemented, they will not appear here.
- **EndToEndTests/** — End-to-end architecture validation is planned for slice S7 (E2E Architecture Validation). Until those gates are implemented, they will not appear here.

Tests in those slices will add their respective subdirectories when their architectural concerns require it. This structure prevents speculative directory creation and keeps the project focused on its current scope.

## Migrated Tests: Assertion Count Verification

The following five tests were migrated from the service's unit-test project into `CapabilityBoundaryGates.cs` and are verified here to confirm no loss of coverage during the move:

| Test Name | Assertion Count | Location |
|-----------|-----------------|----------|
| `IdentityDomain_HasNoProjectReferences` | 1 | `CapabilityBoundaryGates.cs`, method `IdentityDomain_HasNoProjectReferences` |
| `IdentityApplication_OnlyReferencesDomain` | 1 | `CapabilityBoundaryGates.cs`, method `IdentityApplication_OnlyReferencesDomain` |
| `IdentityInfrastructure_NeverReferencedByDomainOrApplication` | 2 | `CapabilityBoundaryGates.cs`, method `IdentityInfrastructure_NeverReferencedByDomainOrApplication` |
| `OnlyIdentityApi_ReferencesInfrastructureDirectly` | 1 | `CapabilityBoundaryGates.cs`, method `OnlyIdentityApi_ReferencesInfrastructureDirectly` |
| `NoCapabilityOtherThanIdentityExistsUnderSrc` | 1 | `CapabilityBoundaryGates.cs`, method `NoCapabilityOtherThanIdentityExistsUnderSrc` |

**Total migrated: 5 tests, 6 assertions**

### Test Execution Verification

As of the most recent full-suite run, `dotnet test` reports the following:
- `ArchitectureTests`: 27 tests passed
- `Identity.UnitTests`: 114 tests passed
- `Identity.IntegrationTests`: 86 tests passed
- **Combined total**: 227 tests

This confirms that the structural boundary-gate tests have been successfully relocated without loss of coverage. Test counts will continue to grow as more gates are added; treat the figures above as a snapshot, not a pinned expectation.

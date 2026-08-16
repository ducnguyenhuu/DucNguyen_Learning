# Architecture Tests

This project contains architecture-enforcement gates that validate layering, dependency boundaries, and other structural constraints across the Tenancy service.

## Scope

The following subdirectories are intentionally absent from this project:

- **ContractTests/** — Contract verification gates are planned for inclusion in slice S9 (Consumer-Contract Testing). Until those gates are implemented, they will not appear here.
- **EndToEndTests/** — End-to-end architecture validation is planned for slice S7 (E2E Architecture Validation). Until those gates are implemented, they will not appear here.

Tests in those slices will add their respective subdirectories when their architectural concerns require it. This structure prevents speculative directory creation and keeps the project focused on its current scope.

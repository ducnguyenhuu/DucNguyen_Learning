# Business Rules

This file contains project-specific business rules and domain logic constraints that should be applied during development.

## How to Use

Add business rules specific to your project domain here. These rules will be referenced by the speckit commands during specification and planning phases.

## Format

### [Rule Category]

- **BR-001**: [Business rule description]
  - Rationale: [Why this rule exists]
  - Exceptions: [When this rule doesn't apply]

## Examples

### Data Integrity

- **BR-001**: Customer IDs must be unique across all tenants
  - Rationale: Required for cross-tenant reporting
  - Exceptions: None

### Authorization

- **BR-002**: Users can only access data within their assigned organization
  - Rationale: Multi-tenant data isolation requirement
  - Exceptions: Super admins can access all organizations

---

**Note**: Delete the examples above and add your own business rules specific to your project.

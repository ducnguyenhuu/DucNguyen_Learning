# AGENTS.md

This file provides guidance to GitHub Copilot's agent mode when working with code in this repository.

## Available Skills

Skills are located in `.claude/skills/` and provide specialized capabilities.

### Rally Skills (`rally.*`)

| Skill | Purpose |
|-------|---------|
| `rally.create-defect` | Create a new Rally defect with name, project, and optional fields (description, severity, priority, owner, environment). Use when the user asks to create a Rally defect, log a bug, or document issues without opening Rally UI. |
| `rally.create-epic` | Create a new Rally epic (portfolio item) with name, project, and optional fields (description, owner, WSJF values, investment category, dates). Use when the user asks to create a Rally epic, define strategic initiatives, or document large-scale work spanning multiple features. |
| `rally.create-feature` | Create a new Rally feature (portfolio item) with name, project, and optional fields (description, owner, WSJF values, dates). Use when the user asks to create a Rally feature, define portfolio work, or document high-level initiatives. |
| `rally.create-story` | Create a new user story in Rally with name, project, and optional fields (description, points, owner). Use when the user asks to create a Rally story, capture requirements as work items, or document features without opening Rally UI. |
| `rally.create-task` | Create a new task in Rally under an existing story or defect with name, parent ID, and optional fields (estimate, owner, description). Use when breaking down stories into implementation tasks or tracking work items. |
| `rally.delete` | Delete Rally items by FormattedID with confirmation prompt. Use when the user explicitly asks to delete or remove Rally work items. IMPORTANT - Deletion is permanent and cannot be undone. |
| `rally.get-item` | Fetch and display Rally work items by FormattedID. Use when the user references Rally items (US####, F####, DE####, etc.) or asks to "get", "show", "fetch", or "look up" Rally items. Supports Features, Epics, User Stories, Tasks, Defects, Test Cases, and more. |
| `rally.get-user` | Get current authenticated Rally user information. Use when the user asks "who am I?", needs their user info, or wants to verify authentication. |
| `rally.list-iterations` | List iterations/sprints for a Rally project. Use when the user asks to see sprints, iterations, or wants to know what iterations are available for a project. |
| `rally.list-templates` | List available templates for a Rally project. Use when the user asks about templates or wants to create items from templates. |
| `rally.manage-tags` | Add, remove, or set tags on Rally items. Use when the user asks to tag items, add labels, or organize work with tags. |
| `rally.query` | Query Rally items with filters (owner, state, completion status). Use when the user asks to find or list Rally items matching specific criteria. |
| `rally.query-tasks` | Query Rally tasks with filters (owner, state, completion status). Use when the user asks to see their tasks, find incomplete work, or filter tasks by specific criteria. |
| `rally.update` | Update Rally items (stories, tasks, features, epics, defects) by FormattedID. Supports updating all fields including state, owner, points, WSJF values, and custom fields. Use when the user asks to modify, change, or update Rally work items. |

### Speckit Skills (`speckit.*`)

| Skill | Purpose |
|-------|---------|
| `speckit.analyze` | Perform a non-destructive cross-artifact consistency and quality analysis across spec.md, plan.md, and tasks.md after task generation. |
| `speckit.checklist` | Generate a custom checklist for the current feature based on user requirements. |
| `speckit.clarify` | Identify underspecified areas in the current feature spec by asking up to 5 highly targeted clarification questions and encoding answers back into the spec. |
| `speckit.constitution` | Create or update the project constitution from interactive or provided principle inputs, ensuring all dependent templates stay in sync. |
| `speckit.help` | Display Speckit workflow commands and their descriptions in a formatted view. |
| `speckit.implement` | Execute the implementation plan by processing and executing all tasks defined in tasks.md |
| `speckit.plan` | Execute the implementation planning workflow using the plan template to generate design artifacts. |
| `speckit.specify` | Create or update the feature specification from a natural language feature description. |
| `speckit.tasks` | Generate an actionable, dependency-ordered tasks.md for the feature based on available design artifacts. |
| `speckit.taskstoissues` | Convert existing tasks into actionable, dependency-ordered GitHub issues for the feature based on available design artifacts. |

### GitHub Skills (`github.*`)

| Skill | Purpose |
|-------|---------|
| `github.add-comment` | Add a comment to a GitHub issue or pull request. Use when the user wants to comment on an issue/PR, provide updates, or reply to discussion. |
| `github.add-reviewers` | Add reviewers to a GitHub pull request. Use after creating a PR or when the user wants to request code review from specific people or teams. |
| `github.create-issue` | Create a new issue in a GitHub repository. Use when the user wants to file a bug report, request a feature, or create a task. |
| `github.create-pr` | Create a new pull request in a GitHub repository. Use when the user wants to open a PR from one branch to another. |
| `github.get-issue` | Fetch a GitHub issue by number. Use when the user wants to view issue details, check issue status, or get information about a specific issue. |
| `github.get-pr` | Fetch a pull request by number from a GitHub repository. Use when the user wants to view PR details, check PR status, or get information about a specific pull request. |
| `github.get-pr-status` | Get the combined CI status for a GitHub pull request. Use when the user wants to check if CI checks are passing, see workflow status, or determine if a PR is ready to merge. |
| `github.get-repo` | Get information about a GitHub repository. Use when the user wants to see repository details, default branch, language, or other repo metadata. |
| `github.list-issues` | List issues for a GitHub repository. Use when the user wants to see open issues, find issues by labels or assignee, or get an overview of issue activity. |
| `github.list-prs` | List pull requests for a GitHub repository. Use when the user wants to see open PRs, find PRs by state, or get an overview of pull request activity. |
| `github.list-workflow-runs` | List GitHub Actions workflow runs for a repository. Use when the user wants to check CI/CD status, see build history, or monitor workflow executions. |
| `github.merge-pr` | Merge a GitHub pull request. Use when the user wants to merge a PR after review and CI checks pass. |
| `github.search-code` | Search for code across GitHub repositories. Use when the user wants to find code patterns, function definitions, or file contents in repositories. |
| `github.search-issues` | Search for issues and pull requests across GitHub. Use when the user wants to find PRs they authored, search for issues by keywords, or find items across repositories. |
| `github.update-pr` | Update an existing GitHub pull request (title, body, state, base branch, draft status). Use when the user wants to modify a PR after creation. |

### SonarQube Skills (`sonar.*`)

| Skill | Purpose |
|-------|---------|
| `sonar.get-coverage` | Get comprehensive code coverage metrics from SonarQube including line coverage, branch coverage, test results, and optional file-level breakdown. Use when the user asks about test coverage, uncovered code, or coverage trends. |
| `sonar.get-duplication` | Get code duplication metrics from SonarQube including duplicated lines, blocks, files, and density. Use when the user asks about code duplication, copy-paste code, or DRY violations. |
| `sonar.get-hotspots` | Get SonarQube security hotspots for a project with filtering by status and resolution. Use when the user asks about security hotspots, security review items, or wants to audit security-sensitive code. |
| `sonar.get-issues` | Get SonarQube issues (bugs, vulnerabilities, code smells) for a project with filtering by type, severity, status, and pull request support. Use when the user asks about code issues, bugs, vulnerabilities, or code smells in SonarQube. |
| `sonar.get-measures` | Get specific SonarQube measures by metric keys with branch support. Use when the user wants particular metrics for a project, or needs to check metrics on a specific branch. |
| `sonar.get-metrics` | Get comprehensive SonarQube project metrics including code quality, security, maintainability, coverage, and complexity. Use when the user wants an overview of project health or asks about SonarQube metrics. |
| `sonar.get-status` | Get SonarQube quality gate status for a project. Use when the user wants to check if a project passes its quality gate, see quality gate conditions, or verify code quality compliance. |
| `sonar.get-uncovered-lines` | Get exact uncovered line numbers and source code from SonarQube for targeted test writing. Use when the user wants to know which specific lines lack test coverage, needs to write tests for uncovered code, or wants a line-level coverage gap analysis. |

### TestRail Skills (`testrail.*`)

| Skill | Purpose |
|-------|---------|
| `testrail.bulk-update-cases` | Bulk update all test cases in a TestRail project/suite. Use when the user wants to apply the same field changes (preconditions, steps, expected results, etc.) to multiple cases at once. Never update titles. |
| `testrail.create-case` | Create a new test case in a TestRail section. Requires project ID, suite ID, and section ID. Validates title uniqueness within the suite before creating. |
| `testrail.create-suite` | Create a new test suite in a TestRail project. Use when the user wants to add a new suite for organizing test cases. |
| `testrail.get-case` | Fetch full details of a single test case by ID, including steps, preconditions, expected results, and custom fields. |
| `testrail.get-cases` | Fetch test cases from a TestRail project. Use when the user asks to see test cases, list tests, or look up TestRail cases for a project. |
| `testrail.get-projects` | List all TestRail projects with their IDs and names. Use when the user needs to find a project ID or see available TestRail projects. |
| `testrail.get-suites` | List test suites for a TestRail project. Use when the user needs to find suite IDs or see available suites before fetching test cases. |
| `testrail.link-cases` | Link TestRail test cases to a Rally story's Test Cases tab. Creates Rally TestCase objects from TestRail case details. TestRail is read-only. |
| `testrail.update-case` | Update a TestRail test case by ID. Use when the user wants to modify a test case's steps, preconditions, expected results, or other fields. Never update the title. |

### Java Skills (`java.*`)

| Skill | Purpose |
|-------|---------|
| `java.test.improve-unit-test-coverage` | Dynamically improve unit test coverage by iteratively adding tests one class at a time. Uses java.test.status output to identify gaps and verify improvements. Never modifies source code — only creates or updates test classes. |
| `java.test.status` | Get current test coverage status from local JaCoCo and PIT (Pitest) reports. Shows line/branch coverage, mutation testing score, and an 80% pass/fail verdict. Use when the user asks about test coverage, mutation score, coverage status, or wants a quality snapshot. |

### Base Tools

| Skill | Purpose |
|-------|---------|
| `clean-dependencies` | Remove, delete, or clean cloned dependencies from the dependencies/ directory. Use when the user asks to remove, delete, clean, or clear dependencies or cloned service repositories. |
| `contribute-skill` | Contribute a local skill to the upstream skills repository by creating a PR. Use when a developer wants to share a custom skill with the wider team/company. |
| `create-skill` | Guide for creating custom skills that extend AI capabilities in this repository. Use when developers want to create a new skill, add a custom workflow, or automate a repetitive task. |
| `fetch-dependency` | Clone a   service repository into the dependencies/ directory for deep code analysis. Use when the user wants to analyze, explore, or work with code from another service. |
| `initialize` | Initialize or update AI assistant configuration files for this project. Use when setting up a new project for AI-assisted development or updating configuration files. |
| `list-skills` | List all available skills with their name, description, and author. Use when the user wants to see installed skills, find what skills are available, or check who created a skill. |
| `sequence` | Generate sequence diagrams from code analysis. Use when the user wants to visualize code flows, document API interactions, or understand method call sequences. |
| `services` | Explore microservice dependencies, fetch OpenAPI specs, and clone service repos for deep analysis. Use when investigating service architecture, API endpoints, or needing to analyze microservice code. |
| `sidecar.report-issue` | Report a bug or request a feature for Sidecar. Use when a user encounters a problem with sidecar skills, wants to suggest improvements, or needs to file an issue against the sidecar project. |

## Using Skills

To use a skill, read its SKILL.md file in `.claude/skills/<skill-name>/` for detailed instructions.

Skills with `scripts/` subdirectories contain executable JavaScript files:

```bash
node .claude/skills/rally.get-item/scripts/get-item.js US12345
```

## Configuration

Set the following environment variables as needed:

- `RALLY_API_KEY` - Rally API authentication
- `GITHUB_TOKEN` - GitHub API access

## Code Style

Follow the project's existing conventions and patterns when making changes.

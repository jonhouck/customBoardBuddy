---
trigger: always_on
---

# Agent Orchestration & Worktree Isolation

**Activation:** Always On
**Description:** Core directives for multi-agent Git worktree isolation, task orchestration, and coding standards.

## 1. Git Worktree Isolation (CRITICAL)
You are part of a multi-agent system. You must NEVER execute file modifications, install dependencies, or run tests directly in the primary repository path. You must operate in complete filesystem isolation to prevent collisions with other agents.

* **Initialization:** Before writing any code, create a new branch for your specific task. 
* **Execution:** Immediately change your current working directory to this new branch. 
* **Completion:** Once your implementation is verified and tests pass, commit your changes to your isolated branch and push to the remote. Provide a diff summary for human review. Do not merge into the main branch yourself.

## 2. Subagent Orchestration & Execution
To prevent context bleed and ensure robust solutions, you must follow a structured, iterative approach:

* **Plan Mode First:** Before modifying any files, analyze the entire project context. You must wrap your initial assessment in `<thinking>` tags and output a step-by-step strategy in `<plan>` tags.
* **Holistic Awareness:** Consider all relevant files, imports, and dependencies. Anticipate how your changes will impact the rest of the architecture.
* **Iterative Verification:** Execute your plan one logical step at a time. You must run tests, linters, or build commands to verify the success of a step before proceeding to the next.
* **File Modifications:** Always read the latest version of a file before applying modifications. Avoid destructive overwrites unless explicitly necessary.

## 3. Coding Best Practices
When generating or refactoring code, adhere to the following standards:

* **Modularity:** Do not dump all logic into a single file. Break down complex functionality into discrete, testable modules (e.g., separate your core logic from your entry points).
* **Explicit over Implicit:** Write clear, self-documenting code. Use descriptive variable names and ensure comments explain the *why* behind complex logic, not just the *what*.
* **Robustness:** Include comprehensive error handling and input validation. Do not swallow exceptions silently.
* **Test-Driven:** Always generate or update corresponding unit tests for any new feature or bug fix. Ensure tests run successfully in your isolated worktree before declaring the task complete.

## 4. Pull Request & Handoff
Once your branch is committed and ready, you must initiate the review process:
* **Create the PR:** Use the GitHub CLI to open a pull request against the main branch (e.g., `gh pr create --title "Brief summary" --body "Detailed explanation of changes, testing done, and linked issues"`).
* **Pause for Review:** Notify the user that the PR is ready and provide the URL. **Do not** attempt to merge the PR yourself. Wait for human approval and merge.

## 5. Post-Merge Reintegration & Cleanup
Once the user confirms the PR has been merged into the remote main branch, you must cleanly dismantle your isolated environment to synchronize the local repository:
1. **Change Directory:** Navigate back to the primary repository path (e.g., `cd ../main-repo`).
2. **Sync Main:** Checkout the main branch and pull the newly merged changes (`git checkout main && git pull`).
# Task Master AI - Claude Code Integration Guide

## Essential Commands

### Core Workflow Commands

```bash
# Project Setup
task-master init                                    # Initialize Task Master in current project
task-master parse-prd .taskmaster/docs/prd.txt      # Generate tasks from PRD document
task-master models --setup                        # Configure AI models interactively

# Daily Development Workflow
task-master list                                   # Show all tasks with status
task-master next                                   # Get next available task to work on
task-master show <id>                             # View detailed task information (e.g., task-master show 1.2)
task-master set-status --id=<id> --status=done    # Mark task complete

# Task Management
task-master add-task --prompt="description" --research        # Add new task with AI assistance
task-master expand --id=<id> --research --force              # Break task into subtasks
task-master update-task --id=<id> --prompt="changes"         # Update specific task
task-master update --from=<id> --prompt="changes"            # Update multiple tasks from ID onwards
task-master update-subtask --id=<id> --prompt="notes"        # Add implementation notes to subtask

# Analysis & Planning
task-master analyze-complexity --research          # Analyze task complexity
task-master complexity-report                      # View complexity analysis
task-master expand --all --research               # Expand all eligible tasks

# Dependencies & Organization
task-master add-dependency --id=<id> --depends-on=<id>       # Add task dependency
task-master move --from=<id> --to=<id>                       # Reorganize task hierarchy
task-master validate-dependencies                            # Check for dependency issues
task-master generate                                         # Update task markdown files (usually auto-called)
```

## Remember Shortcuts
Remember the following shortcuts which the user may invoke at any time.

### QNEW
When I type "qnew", this means:
```
Understand all BEST PRACTICES listed in CLAUDE.md.
Your code SHOULD ALWAYS follow these best practices.
```

### QPLAN
When I type "qplan", this means:
```
Analyze similar parts of the codebase and determine whether your plan:
- is consistent with rest of codebase
- introduces minimal changes
- reuses existing code
```

### QCODE
When I type "qcode", this means:
```
Implement your plan and make sure your new tests pass.
Always run tests to make sure you didn't break anything else.

For TypeScript/JavaScript:
- Run `prettier` on newly created/modified files
- Run `turbo typecheck lint` to ensure type checking and linting passes

For Python:
- Run `black .` or `ruff format` on newly created/modified files  
- Run `ruff check . && mypy .` to ensure linting and type checking passes
```

### QCHECK
When I type "qcheck", this means:
```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR code change you introduced (skip minor changes):
1. CLAUDE.md checklist Writing Functions Best Practices.
2. CLAUDE.md checklist Writing Tests Best Practices.
3. CLAUDE.md checklist Implementation Best Practices.
```

### QCHECKF
When I type "qcheckf", this means:
```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR function you added or edited (skip minor changes):
1. CLAUDE.md checklist Writing Functions Best Practices.
```

### QCHECKT
When I type "qcheckt", this means:
```
You are a SKEPTICAL senior software engineer.
Perform this analysis for every MAJOR test you added or edited (skip minor changes):
1. CLAUDE.md checklist Writing Tests Best Practices.
```

### QUX
When I type "qux", this means:
```
Imagine you are a human UX tester of the feature you implemented. 
Output a comprehensive list of scenarios you would test, sorted by highest priority.
```

### QGIT
When I type "qgit", this means:
```
Add all changes to staging and create a commit following best practices GH-1 and GH-2:
- Use Conventional Commits format (see full details in section 7 - Git)
- Do NOT refer to Claude or Anthropic
- Format: <type>[optional scope]: <description>
- Add [optional body] and [optional footer(s)] as needed
- Use BREAKING CHANGE: footer or ! suffix for breaking changes

Common types: fix, feat, docs, style, refactor, test, chore, build, ci, perf
Note: I will NOT automatically push - you should review and push when ready.
```

### Task Master Shortcuts

### QTASK
When I type "qtask", this means:
```
Show the current task I'm working on using:
task-master show <current-task-id>
```

### QNEXT
When I type "qnext", this means:
```
Get the next available task using:
task-master next
task-master show <returned-id>
```

### QDONE
When I type "qdone", this means:
```
Mark the current task as complete and get the next one:
task-master set-status --id=<current-id> --status=done
task-master next
```

### QLOG
When I type "qlog", this means:
```
Update the current subtask with implementation notes about what I just did:
task-master update-subtask --id=<current-id> --prompt="<summary of changes>"
```

## Implementation Best Practices

### 0 — Purpose  

These rules ensure maintainability, safety, and developer velocity. 
**MUST** rules are enforced by CI; **SHOULD** rules are strongly recommended.

---

### 1 — Before Coding

- **BP-1 (MUST)** Ask the user clarifying questions.
- **BP-2 (SHOULD)** Draft and confirm an approach for complex work.  
- **BP-3 (SHOULD)** If ≥ 2 approaches exist, list clear pros and cons.

---

### 2 — While Coding

- **C-1 (MUST)** Follow TDD: scaffold stub -> write failing test -> implement.
- **C-2 (MUST)** Name functions with existing domain vocabulary for consistency.  
- **C-3 (SHOULD NOT)** Introduce classes when small testable functions suffice.  
- **C-4 (SHOULD)** Prefer simple, composable, testable functions.
- **C-5 (MUST)** Prefer branded `type`s for IDs
  ```ts
  type UserId = Brand<string, 'UserId'>   // ✅ Good
  type UserId = string                    // ❌ Bad
  ```
  
  ```py
  from pydantic import BaseModel

  class UserId(str):                    # ✅ Good - runtime validation
      pass

  # Or with more validation:
  from pydantic import constr

  UserId = constr(min_length=1)        # ✅ Good - with constraints

  user_id: str                          # ❌ Bad - no type safety
  ```
- **C-6 (MUST)** Use `import type { … }` for type-only imports.
  TypeScript: Use import type { … } for type-only imports
  Python: Use from __future__ import annotations and TYPE_CHECKING blocks
  
  ```py
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from .models import User  # ✅ Good - import only for type checking
  ```
- **C-7 (SHOULD NOT)** Add comments except for critical caveats; rely on self‑explanatory code.
- **C-8 (SHOULD)** Default to `type`; use `interface` only when more readable or interface merging is required. 
  TypeScript: Default to type; use interface only when more readable or interface merging is required
  Python: Use TypeAlias for complex types; prefer TypedDict over dict for structured data

  ```py
  from typing import TypeAlias, TypedDict

  UserData: TypeAlias = dict[str, Any]              # ✅ Good for simple aliases
  class UserDict(TypedDict):                         # ✅ Good for structured data
      name: str
      age: int
  ```
- **C-9 (SHOULD NOT)** Extract a new function unless it will be reused elsewhere, is the only way to unit-test otherwise untestable logic, or drastically improves readability of an opaque block.

---

### 3 — Testing

- **T-1 (MUST)** For a simple function, colocate unit tests in the same directory as source file.

  TypeScript: Use *.spec.ts or *.test.ts
  Python: Use test_*.py or *_test.py

- **T-2 (MUST)** For any API change, add/extend integration tests in the appropriate test directory.

  TypeScript: packages/api/test/*.spec.ts
  Python: tests/integration/ or tests/api/

- **T-3 (MUST)** ALWAYS separate pure-logic unit tests from DB-touching integration tests.
- **T-4 (SHOULD)** Prefer integration tests over heavy mocking.
- **T-5 (SHOULD)** Unit-test complex algorithms thoroughly.
- **T-6 (SHOULD)** Test the entire structure in one assertion if possible
  ```ts
  // TypeScript/Jest
  expect(result).toEqual([value])        // ✅ Good
  expect(result).toHaveLength(1);        // ❌ Bad
  expect(result[0]).toBe(value);         // ❌ Bad
  ```

  ```py
  # Python/pytest
  assert result == [value]               # ✅ Good
  assert len(result) == 1                # ❌ Bad
  assert result[0] == value              # ❌ Bad

  # Or with unittest
  self.assertEqual(result, [value])      # ✅ Good
  self.assertEqual(len(result), 1)       # ❌ Bad
  self.assertEqual(result[0], value)     # ❌ Bad
  ```

---

### 4 — Database

- **D-1 (MUST)** Type DB helpers to accept both regular connections and transactions

TypeScript (Kysely):
  ```ts
  type DbConnection = KyselyDatabase | Transaction<Database>
  function getUser(db: DbConnection, id: string) { ... }
  ```
Python (SQLAlchemy):
  ```py
  from sqlalchemy.orm import Session
  from typing import Union

  DbConnection = Union[Session, Session]  # Session handles both
  def get_user(db: DbConnection, user_id: str) -> User: ...
  ```
Python (asyncpg/psycopg):
  ```py
  from typing import Union
  DbConnection = Union[asyncpg.Connection, asyncpg.pool.PoolConnectionProxy]
  # or
  DbConnection = Union[psycopg.Connection, psycopg.Transaction]
  ```
- **D-2 (SHOULD)** Override incorrect auto-generated types in a dedicated override file

TypeScript: Override in packages/shared/src/db-types.override.ts
  ```ts
  // e.g., autogenerated types show incorrect BigInt value
  export type UserId = string  // Override BigInt -> string
  ```

Python: Override in models/overrides.py or similar
  ```py
  # For SQLAlchemy models
  from sqlalchemy import String
  from .generated_models import User as GeneratedUser

  class User(GeneratedUser):
      id: Mapped[str] = mapped_column(String)  # Override BigInt -> str

  # For Pydantic models from OpenAPI
  from .generated_api import UserModel as GeneratedUserModel

  class UserModel(GeneratedUserModel):
      id: str  # Override incorrect type
  ```

---

### 5 — Code Organization

- **O-1 (MUST)** Place code in `packages/shared` only if used by ≥ 2 packages.

---

### 6 — Tooling Gates

- **G-1 (MUST)** Code formatting checks pass

TypeScript: prettier --check
Python: black --check . or ruff format --check

or for a more unified approach:
  ```
  # TypeScript/JavaScript
  prettier --check .

  # Python
  black --check . --diff
  # or
  ruff format --check
  ```

- **G-2 (MUST)** Type checking and linting pass

TypeScript: turbo typecheck lint
Python:
  ```py
  mypy .                    # Type checking
  ruff check .              # Linting
  # Or combined:
  ruff check . && mypy .

or for a more unified approach:
  ```
  # TypeScript/JavaScript
  turbo typecheck lint

  # Python
  ruff check .              # Fast linting + some type checks
  mypy .                    # Type checking
  # or use pre-commit hooks for both
  pre-commit run --all-files
  ```

---

### 7 - Git

- **GH-1 (MUST)** Use Conventional Commits format when writing commit messages: https://www.conventionalcommits.org/en/v1.0.0
  - Structure commit message as follows:
    ```
    <type>[optional scope]: <description>
    [optional body]
    [optional footer(s)]
    ```
  - Commit SHOULD contain the following structural elements to communicate intent:
    - `fix`: patches a bug in your codebase (correlates with PATCH in Semantic Versioning)
    - `feat`: introduces a new feature to the codebase (correlates with MINOR in Semantic Versioning)
    - `BREAKING CHANGE`: a commit that has a footer `BREAKING CHANGE:`, or appends a `!` after the type/scope, introduces a breaking API change (correlating with MAJOR in Semantic Versioning). A BREAKING CHANGE can be part of commits of any type
  - Other types are allowed, for example @commitlint/config-conventional recommends:
    - `build`: Changes that affect the build system or external dependencies
    - `chore`: Other changes that don't modify src or test files
    - `ci`: Changes to CI configuration files and scripts
    - `docs`: Documentation only changes
    - `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc)
    - `refactor`: A code change that neither fixes a bug nor adds a feature
    - `perf`: A code change that improves performance
    - `test`: Adding missing tests or correcting existing tests
  - Footers other than `BREAKING CHANGE: <description>` may be provided and follow a convention similar to git trailer format

- **GH-2 (SHOULD NOT)** Refer to Claude or Anthropic in commit messages.

---

## Writing Functions Best Practices

When evaluating whether a function you implemented is good or not, use this checklist:

1. Can you read the function and HONESTLY easily follow what it's doing? If yes, then stop here.
2. Does the function have very high cyclomatic complexity? (number of independent paths, or, in a lot of cases, number of nesting if if-else as a proxy). If it does, then it's probably sketchy.
3. Are there any common data structures and algorithms that would make this function much easier to follow and more robust? Parsers, trees, stacks / queues, etc.
4. Are there any unused parameters in the function?
5. Are there any unnecessary type casts that can be moved to function arguments?
6. Is the function easily testable without mocking core features (e.g. sql queries, redis, etc.)? If not, can this function be tested as part of an integration test?
7. Does it have any hidden untested dependencies or any values that can be factored out into the arguments instead? Only care about non-trivial dependencies that can actually change or affect the function.
8. Brainstorm 3 better function names and see if the current name is the best, consistent with rest of codebase.

IMPORTANT: you SHOULD NOT refactor out a separate function unless there is a compelling need, such as:
  - the refactored function is used in more than one place
  - the refactored function is easily unit testable while the original function is not AND you can't test it any other way
  - the original function is extremely hard to follow and you resort to putting comments everywhere just to explain it

## Writing Tests Best Practices

When evaluating whether a test you've implemented is good or not, use this checklist:

1. SHOULD parameterize inputs; never embed unexplained literals such as 42 or "foo" directly in the test.
2. SHOULD NOT add a test unless it can fail for a real defect. Trivial asserts (e.g., expect(2).toBe(2)) are forbidden.
3. SHOULD ensure the test description states exactly what the final expect verifies. If the wording and assert don't align, rename or rewrite.
4. SHOULD compare results to independent, pre-computed expectations or to properties of the domain, never to the function's output re-used as the oracle.
5. SHOULD follow the same lint, type-safety, and style rules as prod code (prettier, ESLint, strict types).
6. SHOULD express invariants or axioms (e.g., commutativity, idempotence, round-trip) rather than single hard-coded cases whenever practical. 
TypeScript - Use fast-check:

  ```ts
  import fc from 'fast-check';
  import { describe, expect, test } from 'vitest';
  import { getCharacterCount } from './string';

  describe('properties', () => {
    test('concatenation functoriality', () => {
      fc.assert(
        fc.property(
          fc.string(),
          fc.string(),
          (a, b) =>
            getCharacterCount(a + b) ===
            getCharacterCount(a) + getCharacterCount(b)
        )
      );
    });
  });
  ```

Python - Use hypothesis:
  ```py
  from hypothesis import given, strategies as st
  import pytest
  from .string_utils import get_character_count

  class TestProperties:
      @given(st.text(), st.text())
      def test_concatenation_functoriality(self, a: str, b: str):
          assert get_character_count(a + b) == get_character_count(a) + get_character_count(b)
    
      # Example of other common properties
      @given(st.lists(st.integers()))
      def test_sort_idempotence(self, lst: list[int]):
          assert sorted(sorted(lst)) == sorted(lst)
    
      @given(st.text())
      def test_encode_decode_round_trip(self, text: str):
          assert text.encode('utf-8').decode('utf-8') == text
  ```

7. Unit tests for a function should be grouped together:
TypeScript/Jest:
  ```ts
  describe('functionName', () => {
    test('should handle empty input', () => { ... });
    test('should validate parameters', () => { ... });
  });
  ```

Python/pytest:
  ```py
  class TestFunctionName:
      def test_handles_empty_input(self):
          ...
      def test_validates_parameters(self):
          ...
  # Or with plain functions:
  def test_function_name_handles_empty_input():
      ...
  def test_function_name_validates_parameters():
      ...
  ```

8. Use matchers for variable/unpredictable values:
TypeScript/Jest:
  ```ts
  expect(result).toEqual({
    id: expect.any(String),
    timestamp: expect.any(Number),
    data: 'fixed-value'
  });

Python/pytest:
  ```py
  from unittest.mock import ANY

  assert result == {
    'id': ANY,
    'timestamp': ANY,
    'data': 'fixed-value'
  }
  # Or use partial matching:
  assert result['data'] == 'fixed-value'
  assert isinstance(result['id'], str)
  assert isinstance(result['timestamp'], (int, float)) 

9. ALWAYS use strong assertions over weaker ones 
TypeScript/Jest:
  ```ts
  expect(x).toEqual(1)              // ✅ Good
  expect(x).toBeGreaterThanOrEqual(1)  // ❌ Bad (when you know it's 1)
  ```
Python/pytest:
  ```py
  assert x == 1                     # ✅ Good
  assert x >= 1                     # ❌ Bad (when you know it's 1)

  # With unittest:
  self.assertEqual(x, 1)            # ✅ Good  
  self.assertGreaterEqual(x, 1)     # ❌ Bad (when you know it's 1)
  ```

10. SHOULD test edge cases, realistic input, unexpected input, and value boundaries.
11. SHOULD NOT test conditions that are caught by the type checker.

## Key Files & Project Structure

### Core Files

- `.taskmaster/tasks/tasks.json` - Main task data file (auto-managed)
- `.taskmaster/config.json` - AI model configuration (use `task-master models` to modify)
- `.taskmaster/docs/prd.txt` - Product Requirements Document for parsing
- `.taskmaster/tasks/*.txt` - Individual task files (auto-generated from tasks.json)
- `.env` - API keys for CLI usage

### Claude Code Integration Files

- `CLAUDE.md` - Auto-loaded context for Claude Code (this file)
- `.claude/settings.json` - Claude Code tool allowlist and preferences
- `.claude/commands/` - Custom slash commands for repeated workflows
- `.mcp.json` - MCP server configuration (project-specific)

### Directory Structure

```
project/
├── .taskmaster/
│   ├── tasks/              # Task files directory
│   │   ├── tasks.json      # Main task database
│   │   ├── task-1.md      # Individual task files
│   │   └── task-2.md
│   ├── docs/              # Documentation directory
│   │   ├── prd.txt        # Product requirements
│   ├── reports/           # Analysis reports directory
│   │   └── task-complexity-report.json
│   ├── templates/         # Template files
│   │   └── example_prd.txt  # Example PRD template
│   └── config.json        # AI models & settings
├── .claude/
│   ├── settings.json      # Claude Code configuration
│   └── commands/         # Custom slash commands
├── .env                  # API keys
├── .mcp.json            # MCP configuration
└── CLAUDE.md            # This file - auto-loaded by Claude Code
```

## MCP Integration

Task Master provides an MCP server that Claude Code can connect to. Configure in `.mcp.json`:

```json
{
  "mcpServers": {
    "task-master-ai": {
      "command": "npx",
      "args": ["-y", "--package=task-master-ai", "task-master-ai"],
      "env": {
        "ANTHROPIC_API_KEY": "your_key_here",
        "PERPLEXITY_API_KEY": "your_key_here",
        "OPENAI_API_KEY": "OPENAI_API_KEY_HERE",
        "GOOGLE_API_KEY": "GOOGLE_API_KEY_HERE",
        "XAI_API_KEY": "XAI_API_KEY_HERE",
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY_HERE",
        "MISTRAL_API_KEY": "MISTRAL_API_KEY_HERE",
        "AZURE_OPENAI_API_KEY": "AZURE_OPENAI_API_KEY_HERE",
        "OLLAMA_API_KEY": "OLLAMA_API_KEY_HERE"
      }
    }
  }
}
```

### Essential MCP Tools

```javascript
help; // = shows available taskmaster commands
// Project setup
initialize_project; // = task-master init
parse_prd; // = task-master parse-prd

// Daily workflow
get_tasks; // = task-master list
next_task; // = task-master next
get_task; // = task-master show <id>
set_task_status; // = task-master set-status

// Task management
add_task; // = task-master add-task
expand_task; // = task-master expand
update_task; // = task-master update-task
update_subtask; // = task-master update-subtask
update; // = task-master update

// Analysis
analyze_project_complexity; // = task-master analyze-complexity
complexity_report; // = task-master complexity-report
```

## Claude Code Workflow Integration

### Claude rules to follow
1. First think through the problem, read the codebase for relevant files, and write a plan to tasks/todo.md.
2. The plan should have a list of todo items that you can check off as you complete them
3. Before you begin working, check in with me and I will verify the plan.
4. Then, begin working on the todo items, marking them as complete as you go.
5. Please every step of the way just give me a high level explanation of what changes you made
6. Make every task and code change you do as simple as possible. We want to avoid making any massive or complex changes. Every change should impact as little code as possible. Everything is about simplicity.
7. Finally, add a review section to the [todo.md](http://todo.md/) file with a summary of the changes you made and any other relevant information.


### Standard Development Workflow

#### 1. Project Initialization

```bash
# Initialize Task Master
task-master init

# Create or obtain PRD, then parse it
task-master parse-prd .taskmaster/docs/prd.txt

# Analyze complexity and expand tasks
task-master analyze-complexity --research
task-master expand --all --research
```

If tasks already exist, another PRD can be parsed (with new information only!) using parse-prd with --append flag. This will add the generated tasks to the existing list of tasks..

#### 2. Daily Development Loop

```bash
# Start each session
task-master next                           # Find next available task
task-master show <id>                     # Review task details

# During implementation, check in code context into the tasks and subtasks
task-master update-subtask --id=<id> --prompt="implementation notes..."

# Complete tasks
task-master set-status --id=<id> --status=done
```

#### 3. Multi-Claude Workflows

For complex projects, use multiple Claude Code sessions:

```bash
# Terminal 1: Main implementation
cd project && claude

# Terminal 2: Testing and validation
cd project-test-worktree && claude

# Terminal 3: Documentation updates
cd project-docs-worktree && claude
```

### Custom Slash Commands

Create `.claude/commands/taskmaster-next.md`:

```markdown
Find the next available Task Master task and show its details.

Steps:

1. Run `task-master next` to get the next task
2. If a task is available, run `task-master show <id>` for full details
3. Provide a summary of what needs to be implemented
4. Suggest the first implementation step
```

Create `.claude/commands/taskmaster-complete.md`:

```markdown
Complete a Task Master task: $ARGUMENTS

Steps:

1. Review the current task with `task-master show $ARGUMENTS`
2. Verify all implementation is complete
3. Run any tests related to this task
4. Mark as complete: `task-master set-status --id=$ARGUMENTS --status=done`
5. Show the next available task with `task-master next`
```

## Tool Allowlist Recommendations

Add to `.claude/settings.json`:

```json
{
  "allowedTools": [
    "Edit",
    "Bash(task-master *)",
    "Bash(git commit:*)",
    "Bash(git add:*)",
    "Bash(npm run *)",
    "mcp__task_master_ai__*"
  ]
}
```

## Configuration & Setup

### API Keys Required

At least **one** of these API keys must be configured:

- `ANTHROPIC_API_KEY` (Claude models) - **Recommended**
- `PERPLEXITY_API_KEY` (Research features) - **Highly recommended**
- `OPENAI_API_KEY` (GPT models)
- `GOOGLE_API_KEY` (Gemini models)
- `MISTRAL_API_KEY` (Mistral models)
- `OPENROUTER_API_KEY` (Multiple models)
- `XAI_API_KEY` (Grok models)

An API key is required for any provider used across any of the 3 roles defined in the `models` command.

### Model Configuration

```bash
# Interactive setup (recommended)
task-master models --setup

# Set specific models
task-master models --set-main claude-3-5-sonnet-20241022
task-master models --set-research perplexity-llama-3.1-sonar-large-128k-online
task-master models --set-fallback gpt-4o-mini
```

## Task Structure & IDs

### Task ID Format

- Main tasks: `1`, `2`, `3`, etc.
- Subtasks: `1.1`, `1.2`, `2.1`, etc.
- Sub-subtasks: `1.1.1`, `1.1.2`, etc.

### Task Status Values

- `pending` - Ready to work on
- `in-progress` - Currently being worked on
- `done` - Completed and verified
- `deferred` - Postponed
- `cancelled` - No longer needed
- `blocked` - Waiting on external factors

### Task Fields

```json
{
  "id": "1.2",
  "title": "Implement user authentication",
  "description": "Set up JWT-based auth system",
  "status": "pending",
  "priority": "high",
  "dependencies": ["1.1"],
  "details": "Use bcrypt for hashing, JWT for tokens...",
  "testStrategy": "Unit tests for auth functions, integration tests for login flow",
  "subtasks": []
}
```

## Claude Code Best Practices with Task Master

### Context Management

- Use `/clear` between different tasks to maintain focus
- This CLAUDE.md file is automatically loaded for context
- Use `task-master show <id>` to pull specific task context when needed

### Iterative Implementation

1. `task-master show <subtask-id>` - Understand requirements
2. Explore codebase and plan implementation
3. `task-master update-subtask --id=<id> --prompt="detailed plan"` - Log plan
4. `task-master set-status --id=<id> --status=in-progress` - Start work
5. Implement code following logged plan
6. `task-master update-subtask --id=<id> --prompt="what worked/didn't work"` - Log progress
7. `task-master set-status --id=<id> --status=done` - Complete task

### Complex Workflows with Checklists

For large migrations or multi-step processes:

1. Create a markdown PRD file describing the new changes: `touch task-migration-checklist.md` (prds can be .txt or .md)
2. Use Taskmaster to parse the new prd with `task-master parse-prd --append` (also available in MCP)
3. Use Taskmaster to expand the newly generated tasks into subtasks. Consider using `analyze-complexity` with the correct --to and --from IDs (the new ids) to identify the ideal subtask amounts for each task. Then expand them.
4. Work through items systematically, checking them off as completed
5. Use `task-master update-subtask` to log progress on each task/subtask and/or updating/researching them before/during implementation if getting stuck

### Git Integration

Task Master works well with `gh` CLI:

```bash
# Create PR for completed task
gh pr create --title "Complete task 1.2: User authentication" --body "Implements JWT auth system as specified in task 1.2"

# Reference task in commits
git commit -m "feat: implement JWT auth (task 1.2)"
```

### Parallel Development with Git Worktrees

```bash
# Create worktrees for parallel task development
git worktree add ../project-auth feature/auth-system
git worktree add ../project-api feature/api-refactor

# Run Claude Code in each worktree
cd ../project-auth && claude    # Terminal 1: Auth work
cd ../project-api && claude     # Terminal 2: API work
```

## Troubleshooting

### AI Commands Failing

```bash
# Check API keys are configured
cat .env                           # For CLI usage

# Verify model configuration
task-master models

# Test with different model
task-master models --set-fallback gpt-4o-mini
```

### MCP Connection Issues

- Check `.mcp.json` configuration
- Verify Node.js installation
- Use `--mcp-debug` flag when starting Claude Code
- Use CLI as fallback if MCP unavailable

### Task File Sync Issues

```bash
# Regenerate task files from tasks.json
task-master generate

# Fix dependency issues
task-master fix-dependencies
```

DO NOT RE-INITIALIZE. That will not do anything beyond re-adding the same Taskmaster core files.

## Important Notes

### AI-Powered Operations

These commands make AI calls and may take up to a minute:

- `parse_prd` / `task-master parse-prd`
- `analyze_project_complexity` / `task-master analyze-complexity`
- `expand_task` / `task-master expand`
- `expand_all` / `task-master expand --all`
- `add_task` / `task-master add-task`
- `update` / `task-master update`
- `update_task` / `task-master update-task`
- `update_subtask` / `task-master update-subtask`

### File Management

- Never manually edit `tasks.json` - use commands instead
- Never manually edit `.taskmaster/config.json` - use `task-master models`
- Task markdown files in `tasks/` are auto-generated
- Run `task-master generate` after manual changes to tasks.json

### Claude Code Session Management

- Use `/clear` frequently to maintain focused context
- Create custom slash commands for repeated Task Master workflows
- Configure tool allowlist to streamline permissions
- Use headless mode for automation: `claude -p "task-master next"`

### Multi-Task Updates

- Use `update --from=<id>` to update multiple future tasks
- Use `update-task --id=<id>` for single task updates
- Use `update-subtask --id=<id>` for implementation logging

### Research Mode

- Add `--research` flag for research-based AI enhancement
- Requires a research model API key like Perplexity (`PERPLEXITY_API_KEY`) in environment
- Provides more informed task creation and updates
- Recommended for complex technical tasks

---

_This guide ensures Claude Code has immediate access to Task Master's essential functionality for agentic development workflows._
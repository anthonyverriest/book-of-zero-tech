---
layout: post
title: "Git: a practical workflow"
nav_order: 1
---

Git is the backbone of collaborative development. It also protects reproducibility: you can point to an exact state of code, configs, and decisions that produced a result.

---

## On this page

- [The branch model](#the-branch-model)
- [Setup](#setup)
- [Daily commands](#daily-commands)
- [Commit best practices](#commit-best-practices)
- [Workflow](#workflow)
  - [Feature development](#feature-development)
  - [Promote to release candidate](#promote-to-release-candidate)
  - [Release](#release)
- [State migrations and infrastructure changes](#state-migrations-and-infrastructure-changes)
- [Hotfix](#hotfix)
- [Partial merge](#partial-merge)
- [Cleaning up history](#cleaning-up-history)
- [Stash and undo](#stash-and-undo)
- [Reproducibility](#reproducibility)

---

## The branch model

Use three long-lived branches:

- **`main` (protected)**: what is released. It should not break.
- **`staging` (protected)**: what is about to be released (release candidates). It should not break.
- **`dev` (not protected)**: where day-to-day work integrates. It can break.

Supporting branches:

- **`feat/<topic>`**: feature / experiment branches created from `dev`.
- **`hotfix/<topic>`**: urgent fixes created from `main`.

This gives you speed on `dev` and control on `staging` + `main`.

---

## Setup

- **Clone** an existing repo: `git clone <repository-url>`
- **Or init** a new repo: `git init -b main` (plain `git init` still creates `master` unless `init.defaultBranch` is set), then `git remote add origin <your-repo-url>`
- **Identity** (so commits are attributable): `git config --global user.name "Your Name"`, `git config --global user.email "your.email@example.com"`
- **Pull behavior** (required since Git 2.33.1, otherwise `git pull` refuses to reconcile diverged branches): `git config --global pull.rebase false` (merge) or `true` (rebase)
- **Push behavior** (optional): `git config --global push.autoSetupRemote true` so the first `git push` of a new branch sets its upstream
- **Ignore** local state early via `.gitignore` (see `.gitignore.example`)
  
Sometimes you will also use `.gitattributes` to standardize things like line endings, file treatment, and merge behavior (see `.gitattributes.example`).

### Resources (copy/paste templates)

Use these when you want a strong baseline for repo hygiene without reinventing the “standard ignores” wheel.

<details class="boz-resource">
  <summary><code>.gitignore.example</code></summary>

{% highlight text %}
{% include_relative .gitignore.example %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>.gitattributes.example</code></summary>

{% highlight text %}
{% include_relative .gitattributes.example %}
{% endhighlight %}
</details>

---

## Daily commands

- **What’s going on**: `git status`
- **What changed**: `git diff`, `git diff --staged`
- **History**: `git log --oneline --graph --all`
- **Stage + commit**: `git add <file>`, `git add .`, `git commit -m "feat: short summary"`
- **Sync**: `git pull`, `git push`

If you keep typing the same long commands, add an alias once and use it forever. Create one with `git config --global alias.<name> "<command>"`, for example: `git config --global alias.st status`, `git config --global alias.lg "log --oneline --graph --all"`.

---

## Commit best practices

Treat commits as a project log. A good commit message helps reviewers understand intent and helps you debug and audit later.

Commit types: `feat`, `ref`, `fix`, `test`, `docs`, `chore`, `style`, `data`, `exp`.

### The message format

- Use the pattern `type: short summary`.
- Write the summary in the imperative mood (“add”, “fix”, “remove”, “refactor”).
- Keep it specific to the outcome, not the file names.

### What each type means

- **`feat`**: user-facing capability or pipeline capability added (for example “feat: add batch inference job”).
- **`ref`**: refactor that preserves behavior but improves structure/clarity (for example “ref: split feature engineering into module”).
- **`fix`**: defect correction without changing intended scope (for example “fix: handle empty dataset gracefully”).
- **`test`**: test-only change (for example “test: add regression for leakage bug”).
- **`docs`**: documentation-only change (for example “docs: clarify release process”).
- **`chore`**: maintenance work that is not a feature or fix (for example "chore: bump pre-commit hooks").
- **`style`**: formatting, whitespace, linting, or cosmetic changes with no behavior change (for example "style: apply black formatting to utils module").
- **`data`**: dataset tracking or transformations that change the data contract (for example "data: update schema for customer events v2").
- **`exp`**: AI/ML experiments (for example “exp: compare xgboost vs logistic regression”).

### Practical rules

- Keep commits small and coherent (one intent per commit).
- Prefer committing work that can be reviewed (avoid mixing formatting, refactors, and behavior changes in one commit).
- If something is temporary or broken, keep it on your branch; do not merge it into `dev`.
- Keep branches short-lived and delete them after merge.
- Never commit secrets or large artifacts (use `.gitignore`, Git LFS, or DVC depending on the artifact).

---

## Workflow

### Feature development

Start from `dev` and branch:

- `git switch dev`
- `git pull`
- `git switch -c feat/<topic>`

Work in small commits:

- `git add .`
- `git commit -m "feat: <meaningful summary>"`
- `git push`

The first time you push the branch, use `git push -u origin HEAD` to set its upstream (or enable `push.autoSetupRemote` in Setup), then continue using `git push`.

When ready:

- Sync with `dev` before the PR: `git fetch origin`, then `git merge origin/dev`
- If you hit conflicts, resolve them, stage the resolved files with `git add <file>`, run `git commit` (keep Git's default merge message), then `git push`
- Open a PR: `feat/<topic>` → `dev`
- If `dev` moves during review, re-sync: `git fetch origin`, `git merge origin/dev`, resolve conflicts, then `git push`

### Promote to release candidate

When `dev` is in a releasable state:

- Open a PR: `dev` → `staging`
- Run the checks that matter for production-like validation on `staging`
  
`staging` is protected, so changes land via PR merge (no direct pushes).

### Release

When `staging` is validated:

- Open a PR: `staging` → `main`
- Create the release in GitHub (tag like `v1.2.0`, release notes from PRs)
  
`main` is protected, so releases land via PR merge (no direct pushes).

---

## State migrations and infrastructure changes

State changes are different from code changes: they modify shared resources. Typical examples are database migrations (for example Alembic) and infrastructure changes (for example Terraform). The goal is to keep feature work moving while applying state changes in a controlled, repeatable way.

### Realistic flow

- Do the work on a feature branch like any other change and open a PR to `dev`.
- Apply state changes only after the change lands in `dev`, so a single person or small group can run them consistently without every feature branch touching shared state.
- Promote `dev` → `staging` via PR, then apply the same state changes in the staging environment.
- Promote `staging` → `main` via PR, then apply the same state changes in production.

This keeps state aligned with the code that expects it, without blocking unrelated features on `dev`. It is acceptable for `dev` to break; `staging` and `main` should not.

### Testing from a feature branch

If you need to validate a migration before it merges:

- Use an isolated environment that cannot impact other developers, such as a local database, a dedicated sandbox, or an ephemeral preview environment.

---

## Hotfix

When production is broken, fix from `main`:

- `git switch main`
- `git pull`
- `git switch -c hotfix/<topic>`
- `git add .`
- `git commit -m "fix: <summary>"`
- `git push`

Then:

- Open a PR: `hotfix/<topic>` → `main`
- After merge, sync back so you do not reintroduce the bug:
  - `main` → `staging` (protected): open a PR `main` → `staging` and merge it
  - `main` → `dev` (not protected): `git switch dev`, `git pull`, `git merge main`, `git push`

Direct merge + push is acceptable on `dev` because it is not protected.

---

## Partial merge

When you need specific commits or files on `staging` without promoting everything from `dev`.

### Cherry-pick a commit

- `git switch staging`
- `git pull`
- `git switch -c <type>/<topic>`
- `git cherry-pick -x <commit-hash>`
- `git push`
- Open a PR: `<type>/<topic>` → `staging`

`-x` appends the original hash to the message so you can trace it back.

### Pull a file from another branch

- `git switch staging`
- `git pull`
- `git switch -c <type>/<topic>`
- `git restore --source=origin/dev --staged --worktree path/to/file`
- `git commit -m "<type>: <summary>"`
- `git push`
- Open a PR: `<type>/<topic>` → `staging`

Then promote `staging` → `main` via the normal release PR.

---

## Cleaning up history

Use **squash-merge** for short-lived branches: `feat/*` → `dev` and `hotfix/*` → `main`. This keeps history clean, with one commit per feature. When merging such a PR, select **"Squash and merge"**. This collapses all commits from your feature branch into one commit with a clean message.

Do **not** squash promotion PRs between long-lived branches (`dev` → `staging` → `main`) or the `main` → `dev` sync-back. Squashing rewrites the promoted commits into new ones, so the branches lose their shared history. Every later promotion then re-shows old changes and produces repeated conflicts. Use **"Create a merge commit"** (or a fast-forward) for those PRs.

Commit freely during development, then squash everything when merging.

---

## Stash and undo

- **Temporarily park work**: `git stash`, then later `git stash pop`
- **Discard local edits to a file**: `git restore <file-path>`
- **Undo the last commit (keep changes)**: `git reset --soft HEAD~1`
- **Undo a pushed commit safely**: `git revert <commit-hash>`, then `git push`

---

## Reproducibility

### What to commit

Commit what you can review and what defines reproducibility:

- Code, configs, pipeline definitions, documentation
- Dependency constraints / locks
- Notebooks (ideally with clean diffs)

### What not to commit

Avoid committing:

- Raw/large datasets, model binaries, checkpoints
- Secrets and tokens
- Generated outputs that are easy to reproduce

### Large files

If you need to version large artifacts:

- **Git LFS** (large binaries in Git via pointers): `git lfs install`, `git lfs track "<pattern>"`
- **DVC** (data/model artifacts + remote storage): `dvc init`, `dvc add <data-path>`, then `dvc push`

### Notebooks

If notebook diffs are too noisy:

- Clean outputs: install `nbstripout`, then `nbstripout --install`
- Better diffs: install `nbdime`, then `nbdime config-git --enable`



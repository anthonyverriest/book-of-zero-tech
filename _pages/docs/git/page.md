---
layout: post
title: "Git: a practical workflow"
nav_order: 1
---

A colleague asks which version of the code produced last month's results. If you can answer in ten seconds, Git is doing its job. Git is the backbone of collaborative development. It also protects reproducibility: you can point to the exact state of code, configs, and decisions that produced a result. This guide gives you a workflow that makes both work every day.

---

## On this page

- [Why a workflow matters](#why-a-workflow-matters)
- [Key concepts](#key-concepts)
- [Set up a repository](#set-up-a-repository)
- [The branch model](#the-branch-model)
- [Everyday commands](#everyday-commands)
- [Writing good commits](#writing-good-commits)
  - [The message format](#the-message-format)
  - [What each type means](#what-each-type-means)
  - [Practical rules](#practical-rules)
- [The workflow](#the-workflow)
  - [Feature development](#feature-development)
  - [Promote to a release candidate](#promote-to-a-release-candidate)
  - [Release](#release)
  - [Hotfix](#hotfix)
  - [Choosing a merge strategy](#choosing-a-merge-strategy)
- [Beyond the daily loop](#beyond-the-daily-loop)
  - [State migrations and infrastructure changes](#state-migrations-and-infrastructure-changes)
  - [Partial merges](#partial-merges)
  - [Stash and undo](#stash-and-undo)
  - [Reproducibility](#reproducibility)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)

---

## Why a workflow matters

Picture five people pushing to one branch. Someone's half-finished experiment lands an hour before a release. Nobody can say which commit is in production. Git stores every change, but on its own it does not tell anyone where changes should go.

A workflow is that agreement. It answers three questions before they come up: where do I start work, where does it land, and how does it reach users?

The workflow on this page aims for two things at once. You get speed where people experiment, and control where people depend on the result. Keep that trade-off in mind. Almost every rule below exists to protect it.

---

## Key concepts

- **Long-lived branch**: a branch that exists for the life of the project. This workflow uses three: `main`, `staging`, and `dev`.
- **Protected branch**: a branch that accepts changes only through a merged pull request, never a direct push. Here `main` and `staging` are protected.
- **Supporting branch**: a short-lived branch for one piece of work, named `feat/<topic>` or `hotfix/<topic>`. You delete it after it merges.
- **Upstream**: the remote branch your local branch tracks. Once it is set, a bare `git push` or `git pull` knows where to go.
- **Pull request (PR)**: a request to merge one branch into another, where reviewers and checks see the change before it lands.
- **Squash merge**: a merge that collapses all of a branch's commits into a single new commit.
- **Merge commit**: a merge that keeps the original commits and records where the two histories joined.
- **Cherry-pick**: copying one specific commit onto another branch.
- **Stash**: a shelf where Git parks uncommitted work so you can come back to it later.
- **State change**: a change to a shared resource, such as a database schema or cloud infrastructure, rather than to code alone.
- **Git LFS** and **DVC**: tools for versioning large files that do not belong in Git itself.

---

## Set up a repository

Every project starts in one of two ways. You join one that exists, or you create a new one.

To join an existing project, clone it:

```bash
git clone <repository-url>
```

To start a new one, initialize it and connect it to a remote:

```bash
git init -b main
git remote add origin <your-repo-url>
```

Why `-b main`? Plain `git init` still creates a branch called `master`, unless you have set `init.defaultBranch`. The flag saves you a rename later.

Next, tell Git who you are. Without this, nobody can tell who wrote which commit.

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Now pick how `git pull` behaves when your branch and the remote have both moved. Since Git 2.33.1 this setting is required. Without it, `git pull` refuses to reconcile diverged branches and stops with a complaint instead. Choose merge (`false`) or rebase (`true`):

```bash
git config --global pull.rebase false
```

One more setting is optional but pleasant. With it, the first `git push` of a new branch sets its upstream for you:

```bash
git config --global push.autoSetupRemote true
```

Finally, tell Git what to ignore, and do it early. A **`.gitignore`** keeps local state, such as caches and environment files, out of your history before it sneaks in. Sometimes you will also want a **`.gitattributes`** file. It standardizes line endings, how Git treats certain files, and merge behavior.

### Resources (copy/paste templates)

These give you a strong baseline for repo hygiene, so you do not have to reinvent the "standard ignores" wheel.

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

## The branch model

Go back to those five people on one branch. The release breaks because nothing separates "work in progress" from "about to ship" from "shipped". The fix is to give each of those states its own branch.

This workflow uses three long-lived branches:

- **`main` (protected)**: what is released. It should not break.
- **`staging` (protected)**: what is about to be released, the release candidates. It should not break.
- **`dev` (not protected)**: where day-to-day work integrates. It can break.

Wait, `dev` is allowed to break? Yes, on purpose. Integration is where surprises show up. It is better that they show up on `dev` than on `main`.

Two kinds of supporting branch feed into this model:

- **`feat/<topic>`**: feature and experiment branches, created from `dev`.
- **`hotfix/<topic>`**: urgent fixes, created from `main`.

The result is the trade-off from the start of this guide. You get speed on `dev` and control on `staging` and `main`.

---

## Everyday commands

Most days you will use a handful of commands, over and over:

- **What's going on**: `git status`
- **What changed**: `git diff` for unstaged changes, `git diff --staged` for staged ones
- **History**: `git log --oneline --graph --all`
- **Stage and commit**: `git add <file>` or `git add .`, then `git commit -m "feat: short summary"`
- **Sync**: `git pull`, `git push`

You will type some of these a hundred times a week. When a long command gets tiresome, give it an alias once and use the alias forever. The pattern is `git config --global alias.<name> "<command>"`:

```bash
git config --global alias.st status
git config --global alias.lg "log --oneline --graph --all"
```

Now `git st` and `git lg` do the work.

---

## Writing good commits

Here are two messages for the same change:

```text
updated stuff
fix: handle empty dataset gracefully
```

Six months later, only the second one helps. That is the whole idea: treat commits as a project log. A good message helps reviewers understand your intent. It also helps you debug and audit later, when you have long forgotten the details.

This workflow uses nine commit types: `feat`, `ref`, `fix`, `test`, `docs`, `chore`, `style`, `data`, and `exp`.

### The message format

The message pattern is `type: short summary`. Three rules make the summary useful:

- Write it in the imperative mood: "add", "fix", "remove", "refactor". Read it as "this commit will…".
- Describe the outcome, not the file names. The diff already lists the files.
- Keep it specific. "fix: handle empty dataset gracefully" beats "fix: bug".

### What each type means

- **`feat`**: a user-facing or pipeline capability is added (for example "feat: add batch inference job").
- **`ref`**: a refactor that preserves behavior but improves structure or clarity (for example "ref: split feature engineering into module").
- **`fix`**: a defect correction that does not change the intended scope (for example "fix: handle empty dataset gracefully").
- **`test`**: a test-only change (for example "test: add regression for leakage bug").
- **`docs`**: a documentation-only change (for example "docs: clarify release process").
- **`chore`**: maintenance that is neither a feature nor a fix (for example "chore: bump pre-commit hooks").
- **`style`**: formatting, whitespace, linting, or cosmetic changes with no behavior change (for example "style: apply black formatting to utils module").
- **`data`**: dataset tracking or transformations that change the data contract (for example "data: update schema for customer events v2").
- **`exp`**: AI/ML experiments (for example "exp: compare xgboost vs logistic regression").

### Practical rules

Imagine reviewing one commit that reformats a file, renames a function, and changes a calculation. Which line changed the result? You cannot tell without reading everything. These rules prevent that:

- Keep commits small and coherent, with one intent per commit.
- Commit work that someone can review. Do not mix formatting, refactors, and behavior changes in one commit.
- If something is temporary or broken, keep it on your branch. Do not merge it into `dev`.
- Keep branches short-lived, and delete them after they merge.
- Never commit secrets or large artifacts. Use `.gitignore`, Git LFS, or DVC, depending on the artifact.

---

## The workflow

You know the branches and how to write commits. Now follow one change from your laptop to production.

### Feature development

Start from an up-to-date `dev` and create your branch:

```bash
git switch dev
git pull
git switch -c feat/<topic>
```

Work in small commits:

```bash
git add .
git commit -m "feat: <meaningful summary>"
git push
```

The first push of a new branch has a catch. Git does not know where to send it yet, because the branch has no upstream. Set one with `git push -u origin HEAD`, or turn on `push.autoSetupRemote` as shown in [Set up a repository](#set-up-a-repository). After that, a bare `git push` works.

When your feature is ready, bring in whatever landed on `dev` while you worked. That way any conflicts surface on your branch, not in the PR:

```bash
git fetch origin
git merge origin/dev
```

Hit conflicts? Resolve them in the files, stage each resolved file with `git add <file>`, then run `git commit`. Keep Git's default merge message, since it already says what happened. Then `git push`.

Now open a PR from `feat/<topic>` to `dev`.

Reviews take time, and `dev` may move during yours. If it does, re-sync the same way: `git fetch origin`, `git merge origin/dev`, resolve any conflicts, then `git push`.

### Promote to a release candidate

When `dev` is in a releasable state:

1. Open a PR from `dev` to `staging`.
2. Run the checks that matter for production-like validation on `staging`.

Because `staging` is protected, changes land through a PR merge. Nobody pushes to it directly.

### Release

When `staging` is validated:

1. Open a PR from `staging` to `main`.
2. Create the release in GitHub, with a tag like `v1.2.0` and release notes drawn from the PRs.

Because `main` is protected, releases land through a PR merge, never a direct push.

### Hotfix

Production is broken, and the fix cannot wait for the next trip through `dev` and `staging`. So you start from the code that is actually running, `main`:

```bash
git switch main
git pull
git switch -c hotfix/<topic>
git add .
git commit -m "fix: <summary>"
git push
```

Open a PR from `hotfix/<topic>` to `main`.

You are not done when it merges. The fix now exists on `main` and nowhere else. If you stop here, the next promotion from `dev` brings the bug right back. Sync the fix back to both branches:

- **`main` → `staging`** (protected): open a PR from `main` to `staging` and merge it.
- **`main` → `dev`** (not protected): merge it directly.

```bash
git switch dev
git pull
git merge main
git push
```

A direct merge and push is acceptable on `dev` because `dev` is not protected.

### Choosing a merge strategy

Your feature branch probably has commits like "wip", "fix typo", and "try again". Nobody needs those on `dev` forever.

For short-lived branches, `feat/*` into `dev` and `hotfix/*` into `main`, use a **squash merge**. When you merge the PR, select **"Squash and merge"**. This collapses all of the branch's commits into one commit with a clean message. History stays clean, with one commit per feature. So commit freely while you develop, and squash everything when you merge.

Long-lived branches are a different story. Do **not** squash promotion PRs (`dev` → `staging` → `main`) or the `main` → `dev` sync-back. Why not? Squashing rewrites the promoted commits into new ones, so the branches lose their shared history. Git then sees old changes as new on every later promotion, and you resolve the same conflicts again and again. For these PRs, use **"Create a merge commit"**, or a fast-forward.

---

## Beyond the daily loop

The loop above covers most days. The sections below cover the situations that come up less often but cost more when you get them wrong.

### State migrations and infrastructure changes

Code changes only touch files. Running a database migration (for example with Alembic) or an infrastructure change (for example with Terraform) modifies shared resources that everyone uses. You cannot fix that kind of change by switching branches.

The goal is to keep feature work moving while you apply state changes in a controlled, repeatable way. Here is a realistic flow:

1. Do the work on a feature branch like any other change, and open a PR to `dev`.
2. Apply the state change only after it lands in `dev`. Then one person or a small group can run it consistently, instead of every feature branch touching shared state.
3. Promote `dev` to `staging` through a PR, then apply the same state change in the staging environment.
4. Promote `staging` to `main` through a PR, then apply the same state change in production.

This keeps state aligned with the code that expects it, without blocking unrelated features on `dev`. It is acceptable for `dev` to break. `staging` and `main` should not.

What if you need to validate a migration before it merges? Test it in an isolated environment that cannot affect other developers. A local database, a dedicated sandbox, or an ephemeral preview environment all work.

### Partial merges

Sometimes `staging` needs one fix from `dev`, but not everything else that is sitting there. Promoting all of `dev` would ship work that is not ready. You need a partial merge: specific commits or files, nothing more.

To bring over a single commit, **cherry-pick** it onto a branch made from `staging`:

```bash
git switch staging
git pull
git switch -c <type>/<topic>
git cherry-pick -x <commit-hash>
git push
```

Then open a PR from `<type>/<topic>` to `staging`. The `-x` flag appends the original commit's hash to the message, so you can trace the copy back to where it came from.

To bring over one file as it exists on `dev`, restore it from there:

```bash
git switch staging
git pull
git switch -c <type>/<topic>
git restore --source=origin/dev --staged --worktree path/to/file
git commit -m "<type>: <summary>"
git push
```

Then open a PR from `<type>/<topic>` to `staging`.

Either way, the change then reaches `main` through the normal release PR from `staging` to `main`.

### Stash and undo

Everyone needs an escape hatch now and then. Here is the one for each situation:

- **You need a clean tree for a minute, but you are mid-change**: park the work with `git stash`, and bring it back later with `git stash pop`.
- **You edited a file and want the original back**: `git restore <file-path>` discards your local edits.
- **You committed too soon**: `git reset --soft HEAD~1` undoes the last commit and keeps its changes.
- **You already pushed a bad commit**: `git revert <commit-hash>`, then `git push`. This adds a new commit that undoes the old one, which is the safe way to undo pushed work.

### Reproducibility

Remember the opening question: which version produced that result? You can answer it only if the right things live in Git.

Commit what you can review and what defines reproducibility:

- Code, configs, pipeline definitions, and documentation
- Dependency constraints and lock files
- Notebooks, ideally with clean diffs

Keep these out:

- Raw or large datasets, model binaries, and checkpoints
- Secrets and tokens
- Generated outputs that you can cheaply regenerate

But what if you do need to version a large artifact? Use a tool built for it:

- **Git LFS** stores large binaries in Git through lightweight pointers. Set it up with `git lfs install`, then `git lfs track "<pattern>"`.
- **DVC** versions data and model artifacts and keeps them in remote storage. Run `dvc init`, then `dvc add <data-path>`, then `dvc push`.

Notebooks have their own problem. Their diffs fill up with outputs and metadata, which buries the change you made. If the noise gets too loud:

- **Clean outputs**: install `nbstripout`, then run `nbstripout --install`.
- **Better diffs**: install `nbdime`, then run `nbdime config-git --enable`.

---

## Common pitfalls

Everything here appears earlier in the guide. These are the mistakes people make most often:

- **`git pull` refuses to run.** Your branch and the remote have diverged, and you have not set `pull.rebase`. Since Git 2.33.1 that setting is required.
- **Your new repo has a `master` branch.** Plain `git init` creates `master` unless `init.defaultBranch` is set. Use `git init -b main`.
- **The first push fails on a new branch.** The branch has no upstream yet. Use `git push -u origin HEAD`, or enable `push.autoSetupRemote`.
- **The same conflicts come back on every release.** Someone squashed a promotion PR or the sync-back, and the branches lost their shared history. Use a merge commit for those PRs.
- **A fixed bug reappears.** A hotfix merged into `main` but never synced back to `staging` and `dev`.
- **`dev` is broken for everyone.** Temporary or broken work was merged from a feature branch. Keep it on your branch until it works.
- **Shared state drifts.** Feature branches applied migrations or infrastructure changes. Apply them only after the change lands in `dev`, and test earlier work in an isolated environment.
- **A secret or a huge file ends up in history.** Set up `.gitignore` early, and use Git LFS or DVC for large artifacts.

---

## Recap

- Use three long-lived branches: `dev` can break, while `staging` and `main` are protected and should not.
- Start features from `dev` and hotfixes from `main`, and keep supporting branches short-lived.
- Set `pull.rebase`, your identity, and `.gitignore` before your first commit.
- Write commits as `type: short summary` in the imperative, with one intent per commit.
- Sync with `git fetch origin` and `git merge origin/dev` before and during a PR.
- Squash short-lived branches, and use merge commits for promotions and sync-backs.
- Sync every hotfix back to `staging` and `dev`.
- Apply state changes only after they land in `dev`, then once per environment.
- Commit what defines reproducibility, and keep large artifacts in Git LFS or DVC.

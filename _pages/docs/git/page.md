---
layout: post
title: "Git: a practical workflow"
nav_order: 1
---

A colleague asks which version of the code produced last month's churn report. Can you answer in ten seconds? That is the real question this page answers: how does a team change one project every day and still know exactly what produced each result and what is running in production?

That question is big, so we start with a smaller one: how do **two people** change the same project without stepping on each other? Once that works, the answer for five people, a release process, and an emergency fix follows from the same idea.

We will follow one small team through the whole guide. Ana and Ben maintain `churn-model`, a Python project that trains a customer churn classifier and ships it as a batch job. In six parts, we set up their repository, give their work a shape, and follow one change all the way to production.

---

## On this page

- [Key concepts](#key-concepts)
- [Part 1: A repository remembers everything, once you tell it who you are](#part-1-a-repository-remembers-everything-once-you-tell-it-who-you-are)
  - [Resources (copy/paste templates)](#resources-copypaste-templates)
- [Part 2: Separate branches keep unfinished work away from shipped work](#part-2-separate-branches-keep-unfinished-work-away-from-shipped-work)
- [Part 3: A handful of commands cover most days](#part-3-a-handful-of-commands-cover-most-days)
- [Part 4: A commit message is a note to your future self](#part-4-a-commit-message-is-a-note-to-your-future-self)
  - [The message format](#the-message-format)
  - [What each type means](#what-each-type-means)
  - [One intent per commit](#one-intent-per-commit)
- [Part 5: One change travels from a laptop to production](#part-5-one-change-travels-from-a-laptop-to-production)
  - [Feature development](#feature-development)
  - [Promote to a release candidate](#promote-to-a-release-candidate)
  - [Release](#release)
  - [Hotfix](#hotfix)
  - [Choosing a merge strategy](#choosing-a-merge-strategy)
- [Part 6: Some changes live outside the code](#part-6-some-changes-live-outside-the-code)
  - [State migrations and infrastructure changes](#state-migrations-and-infrastructure-changes)
  - [Partial merges](#partial-merges)
  - [Stash and undo](#stash-and-undo)
  - [Reproducibility](#reproducibility)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)
- [Exercise](#exercise)

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

## Part 1: A repository remembers everything, once you tell it who you are

Before Ana and Ben can share anything, they need a repository, and Git needs to know who is writing each change. A project starts in one of two ways. You join one that exists, or you create a new one.

Ben joins the existing project, so he clones it:

```bash
git clone <repository-url>
```

Ana started the project, so she initialized it and connected it to a remote:

```bash
git init -b main
git remote add origin <your-repo-url>
```

Why `-b main`? Plain `git init` still creates a branch called `master`, unless you have set `init.defaultBranch`. The flag saves you a rename later.

Next, each of them tells Git who they are. Without this, nobody can tell who wrote which commit, and "who changed the threshold?" has no answer.

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

Now a question that seems premature: what should `git pull` do when Ana's copy and the remote have both moved? It matters on day one. Since Git 2.33.1 this setting is required. Without it, `git pull` refuses to reconcile diverged branches and stops with a complaint instead. Choose merge (`false`) or rebase (`true`):

```bash
git config --global pull.rebase false
```

One more setting is optional but pleasant. With it, the first `git push` of a new branch sets its upstream for you:

```bash
git config --global push.autoSetupRemote true
```

Think of the upstream as a default delivery address. Once it is on file, you stop writing it on every package.

Finally, tell Git what to ignore, and do it early. A **`.gitignore`** keeps local state, such as caches and environment files, out of your history before it sneaks in. Sometimes you will also want a **`.gitattributes`** file. It standardizes line endings, how Git treats certain files, and merge behavior.

What `.gitignore` does not do: it does not remove a file that is already committed. It only stops new, untracked files from being added. That is why "early" matters.

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

**Set your identity, `pull.rebase`, and `.gitignore` before the first commit, because each one is painful to fix afterwards.**

---

## Part 2: Separate branches keep unfinished work away from shipped work

Start with one person. Ana alone on `main` has no conflicts to worry about. Every commit is hers, and the latest one is the truth.

Now add Ben. Ana is halfway through a new feature that does not run yet. Ben pushes a one-line fix to the same branch and wants to ship it. He cannot ship his fix without also shipping her half-finished feature, because they live on the same line of history.

Now picture five people on that one branch. Someone's half-finished experiment lands an hour before a release. Nobody can say which commit is in production. Git stores every change, but on its own it does not tell anyone where changes should go. A **workflow** is that agreement.

The problem in every case is the same. Nothing separates "work in progress" from "about to ship" from "shipped". The fix is to give each of those states its own branch.

This workflow uses three long-lived branches:

- **`main` (protected)**: what is released. It should not break.
- **`staging` (protected)**: what is about to be released, the release candidates. It should not break.
- **`dev` (not protected)**: where day-to-day work integrates. It can break.

Wait, `dev` is allowed to break? Yes, on purpose. Integration is where surprises show up. It is better that they show up on `dev` than on `main`.

Two kinds of supporting branch feed into this model:

- **`feat/<topic>`**: feature and experiment branches, created from `dev`.
- **`hotfix/<topic>`**: urgent fixes, created from `main`.

An analogy helps here. `dev` is the kitchen, `staging` is the pass where the head chef checks each plate, and `main` is the dining room. Mess is fine in the kitchen. Nothing reaches a guest without passing the check.

What protection does not tell you: a protected branch guarantees that a review happened, not that the change is correct. The checks and the reviewer still do the real work.

**Each branch holds one level of readiness, which gives you speed on `dev` and control on `staging` and `main`.**

---

## Part 3: A handful of commands cover most days

Ana's day mostly repeats the same five moves: look, compare, record, share, catch up.

- **What's going on**: `git status`
- **What changed**: `git diff` for unstaged changes, `git diff --staged` for staged ones
- **History**: `git log --oneline --graph --all`
- **Stage and commit**: `git add <file>` or `git add .`, then `git commit -m "feat: short summary"`
- **Sync**: `git pull`, `git push`

A common confusion: why does `git diff` sometimes show nothing after you edited a file? Because you already staged it. `git diff` compares your files to the staging area, so staged edits appear only under `git diff --staged`.

You will type some of these a hundred times a week. When a long command gets tiresome, give it an alias once and use the alias forever. The pattern is `git config --global alias.<name> "<command>"`:

```bash
git config --global alias.st status
git config --global alias.lg "log --oneline --graph --all"
```

Now `git st` and `git lg` do the work.

**Five commands, plus a couple of aliases, carry most of your daily Git work.**

---

## Part 4: A commit message is a note to your future self

Six months from now, the churn model's recall drops, and Ben goes looking for the cause. Here are two messages for the same change:

```text
updated stuff
fix: handle empty dataset gracefully
```

Only the second one helps him. That is the whole idea: treat commits as a project log. A good message helps reviewers understand your intent. It also helps you debug and audit later, when you have long forgotten the details.

This workflow uses nine commit types: `feat`, `ref`, `fix`, `test`, `docs`, `chore`, `style`, `data`, and `exp`.

### The message format

The message pattern is `type: short summary`. Three rules make the summary useful:

- Write it in the imperative mood: "add", "fix", "remove", "refactor". Read it as "this commit will…".
- Describe the outcome, not the file names. The diff already lists the files.
- Keep it specific. "fix: handle empty dataset gracefully" beats "fix: bug".

**The type says what kind of change it is; the summary says what it achieves.**

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

Unsure between `ref` and `fix`? Ask whether behavior changed. If the output is the same before and after, it is a `ref`.

**Pick the type by what the change does to behavior, not by which files it touches.**

### One intent per commit

Imagine Ben reviewing one commit that reformats a file, renames a function, and changes a calculation. Three hundred lines changed. Which one moved the recall? He cannot tell without reading everything.

Now split that commit into three. The `style` commit and the `ref` commit change no behavior, so he skims them. The one `fix` commit with eight changed lines is where the result moved. Same work, a fraction of the review.

These rules keep commits like that:

- Keep commits small and coherent, with one intent per commit.
- Commit work that someone can review. Do not mix formatting, refactors, and behavior changes in one commit.
- If something is temporary or broken, keep it on your branch. Do not merge it into `dev`.
- Keep branches short-lived, and delete them after they merge.
- Never commit secrets or large artifacts. Use `.gitignore`, Git LFS, or DVC, depending on the artifact.

What a good message does not tell you: whether the change is correct. It tells you what the author intended, which is what you need to check it.

**One intent per commit turns a history into something you can search, review, and undo piece by piece.**

**So far:** Ana and Ben have a configured repository, three branches that each hold one level of readiness, a small set of daily commands, and commit messages that explain themselves. Next, we move a real change through those branches.

---

## Part 5: One change travels from a laptop to production

Ana wants to add a batch inference job to `churn-model`. We follow that one change from her laptop to production, then handle the day something breaks.

### Feature development

She starts from an up-to-date `dev` and creates her branch:

```bash
git switch dev
git pull
git switch -c feat/<topic>
```

She works in small commits:

```bash
git add .
git commit -m "feat: <meaningful summary>"
git push
```

The first push of a new branch has a catch. Git does not know where to send it yet, because the branch has no upstream. Set one with `git push -u origin HEAD`, or turn on `push.autoSetupRemote` as shown in [Part 1](#part-1-a-repository-remembers-everything-once-you-tell-it-who-you-are). After that, a bare `git push` works.

While she worked, Ben merged two fixes into `dev`. Before her PR, she brings them in, so any conflicts surface on her branch, not in the PR:

```bash
git fetch origin
git merge origin/dev
```

Hit conflicts? Resolve them in the files, stage each resolved file with `git add <file>`, then run `git commit`. Keep Git's default merge message, since it already says what happened. Then `git push`.

Now she opens a PR from `feat/<topic>` to `dev`.

Reviews take time, and `dev` may move during hers. If it does, she re-syncs the same way: `git fetch origin`, `git merge origin/dev`, resolve any conflicts, then `git push`.

**Sync with `dev` before and during a PR, so conflicts land on your branch instead of in review.**

### Promote to a release candidate

A week later, `dev` holds Ana's job, Ben's fixes, and two small features. When `dev` is in a releasable state:

1. Open a PR from `dev` to `staging`.
2. Run the checks that matter for production-like validation on `staging`.

Because `staging` is protected, changes land through a PR merge. Nobody pushes to it directly.

**`staging` is where a bundle of changes proves it is ready, before any user sees it.**

### Release

When `staging` is validated:

1. Open a PR from `staging` to `main`.
2. Create the release in GitHub, with a tag like `v1.2.0` and release notes drawn from the PRs.

Because `main` is protected, releases land through a PR merge, never a direct push.

The tag is what answers the opening question. "Last month's report came from `v1.2.0`" points to one exact state of the code.

**A tagged release on `main` gives every result a version you can name.**

### Hotfix

Two days after `v1.2.0`, the batch job crashes on customers with no events. Production is broken, and the fix cannot wait for the next trip through `dev` and `staging`. So Ben starts from the code that is actually running, `main`:

```bash
git switch main
git pull
git switch -c hotfix/<topic>
git add .
git commit -m "fix: <summary>"
git push
```

He opens a PR from `hotfix/<topic>` to `main`.

You might expect the story to end when it merges. It does not. The fix now exists on `main` and nowhere else. If he stops here, the next promotion from `dev` brings the bug right back, because `dev` never received the fix. So he syncs it back to both branches:

- **`main` → `staging`** (protected): open a PR from `main` to `staging` and merge it.
- **`main` → `dev`** (not protected): merge it directly.

```bash
git switch dev
git pull
git merge main
git push
```

A direct merge and push is acceptable on `dev` because `dev` is not protected.

**A hotfix is finished only when it exists on `main`, `staging`, and `dev`.**

### Choosing a merge strategy

Ana's feature branch has commits like "wip", "fix typo", and "try again". Nobody needs those on `dev` forever.

For short-lived branches, `feat/*` into `dev` and `hotfix/*` into `main`, use a **squash merge**. When you merge the PR, select **"Squash and merge"**. This collapses all of the branch's commits into one commit with a clean message. Ana's twelve commits become one, so `dev` gets one commit per feature. Commit freely while you develop, and squash everything when you merge.

That works so well that the natural next step is to squash every PR, including `dev` → `staging`. Here is where the expectation fails.

Squashing writes a brand-new commit with new contents and no link to the originals. Suppose `dev` has commits A, B, C, and you squash them into `staging` as S. Git does not know that S equals A + B + C. On the next promotion, `dev` still has A, B, C, and `staging` has S, so Git sees two unrelated histories that both changed the same lines. You resolve the same conflicts again, and again on every later promotion.

So long-lived branches follow a different rule. Do **not** squash promotion PRs (`dev` → `staging` → `main`) or the `main` → `dev` sync-back. For these PRs, use **"Create a merge commit"**, or a fast-forward. Both keep the shared history, so Git knows what each branch already has.

**Squash short-lived branches for a clean history; keep merge commits between long-lived branches so their histories stay connected.**

**So far:** a feature starts on `feat/*` from `dev`, gets synced and reviewed, moves to `staging` as a release candidate, and reaches `main` as a tagged release. A hotfix runs the same path in reverse, starting from `main` and syncing back. Next, we handle the changes that Git alone cannot roll back.

---

## Part 6: Some changes live outside the code

The loop above covers most days. This part covers the situations that come up less often but cost more when you get them wrong.

### State migrations and infrastructure changes

Ana's batch job needs a new `predictions` table. Code changes only touch files. Running a database migration (for example with Alembic) or an infrastructure change (for example with Terraform) modifies shared resources that everyone uses. You cannot undo that kind of change by switching branches.

Now picture both Ana and Ben applying their own migrations from their feature branches to the shared database. The schema ends up matching neither branch. The goal is to keep feature work moving while you apply state changes in a controlled, repeatable way. Here is a realistic flow:

1. Do the work on a feature branch like any other change, and open a PR to `dev`.
2. Apply the state change only after it lands in `dev`. Then one person or a small group can run it consistently, instead of every feature branch touching shared state.
3. Promote `dev` to `staging` through a PR, then apply the same state change in the staging environment.
4. Promote `staging` to `main` through a PR, then apply the same state change in production.

This keeps state aligned with the code that expects it, without blocking unrelated features on `dev`. It is acceptable for `dev` to break. `staging` and `main` should not.

What if you need to validate a migration before it merges? Test it in an isolated environment that cannot affect other developers. A local database, a dedicated sandbox, or an ephemeral preview environment all work.

**Apply state changes once per environment, after the code that needs them has landed there.**

### Partial merges

Sometimes `staging` needs Ben's one fix from `dev`, but not everything else sitting there. Promoting all of `dev` would ship work that is not ready. You need a partial merge: specific commits or files, nothing more.

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

**Cherry-pick a commit or restore a file when `staging` needs one change, not all of `dev`.**

### Stash and undo

Everyone needs an escape hatch now and then. Here is the one for each situation:

- **You need a clean tree for a minute, but you are mid-change**: park the work with `git stash`, and bring it back later with `git stash pop`.
- **You edited a file and want the original back**: `git restore <file-path>` discards your local edits.
- **You committed too soon**: `git reset --soft HEAD~1` undoes the last commit and keeps its changes.
- **You already pushed a bad commit**: `git revert <commit-hash>`, then `git push`. This adds a new commit that undoes the old one, which is the safe way to undo pushed work.

Why not `reset` a pushed commit too? Because Ben may already have it. Rewriting shared history leaves his copy and the remote disagreeing. `revert` adds to history instead of rewriting it, so everyone stays in sync.

**Undo local work freely; undo shared work with `git revert`.**

### Reproducibility

Back to the opening question: which version produced last month's report? The tag points to the code. But the answer is complete only if the right things live in Git.

Commit what you can review and what defines reproducibility:

- Code, configs, pipeline definitions, and documentation
- Dependency constraints and lock files
- Notebooks, ideally with clean diffs

Keep these out:

- Raw or large datasets, model binaries, and checkpoints
- Secrets and tokens
- Generated outputs that you can cheaply regenerate

But the churn model was trained on a specific dataset, and that dataset is too large for Git. Use a tool built for it:

- **Git LFS** stores large binaries in Git through lightweight pointers. Set it up with `git lfs install`, then `git lfs track "<pattern>"`.
- **DVC** versions data and model artifacts and keeps them in remote storage. Run `dvc init`, then `dvc add <data-path>`, then `dvc push`.

Both put a small pointer file in Git and the heavy file elsewhere. The commit still pins the exact version, without the repository growing by gigabytes.

Notebooks have their own problem. Their diffs fill up with outputs and metadata, which buries the change you made. If the noise gets too loud:

- **Clean outputs**: install `nbstripout`, then run `nbstripout --install`.
- **Better diffs**: install `nbdime`, then run `nbdime config-git --enable`.

What Git does not tell you: the environment a result ran in, such as the machine, the random seed, or the data pulled at run time. Pin those in configs and lock files you commit, or the code version alone will not reproduce the number.

**A result is reproducible when its code, configs, dependencies, and data pointers are all pinned to one commit.**

**So far:** state changes go out once per environment, partial merges move one change at a time, undo depends on whether work is shared, and reproducibility depends on what you choose to commit.

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

- Set `pull.rebase`, your identity, and `.gitignore` before your first commit.
- Use three long-lived branches: `dev` can break, while `staging` and `main` are protected and should not.
- Start features from `dev` and hotfixes from `main`, and keep supporting branches short-lived.
- Write commits as `type: short summary` in the imperative, with one intent per commit.
- Sync with `git fetch origin` and `git merge origin/dev` before and during a PR.
- Squash short-lived branches, and use merge commits for promotions and sync-backs.
- Sync every hotfix back to `staging` and `dev`.
- Apply state changes only after they land in `dev`, then once per environment.
- Commit what defines reproducibility, and keep large artifacts in Git LFS or DVC.

---

## Exercise

In a scratch directory, create a repository with `git init -b main`, add one file, and commit it. Create `dev` from `main`, then a `feat/greeting` branch from `dev`. Make three small commits on `feat/greeting`, then squash-merge it into `dev` with `git merge --squash feat/greeting` followed by `git commit`. Run `git log --oneline --graph --all` and count the commits on `dev`. You should see one new commit, not three. Then ask yourself: what would happen to the next `dev` → `main` merge if you squashed that one too?

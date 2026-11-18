---
layout: post
title: "Docker: containerize a Python project"
nav_order: 2
---

You have probably heard "it works on my machine". Maybe you have said it. The code is fine, but your laptop has one Python version, the CI runner has another, and production has a library nobody remembers installing. The real question behind that phrase is this: how do you make sure the software you tested is exactly the software that runs everywhere else?

We start with a smaller version of it: how do you run one Python service on a second machine and get the same behavior as on the first? **Docker** answers it by packaging code and dependencies into a single runnable unit. You build it once, and every environment runs that same unit.

Our example is `churn-api`, a small Python service that serves churn predictions on port 8080. In seven parts, we build an image for it, run it safely, read the reference Dockerfile line by line, ship it from CI, and operate it. This page focuses on building images and running containers. For orchestrating services locally, see [Docker Compose: orchestrate local development]({{ site.baseurl }}/docs/containerization/docker-compose/page/).

---

## On this page

- [Key concepts](#key-concepts)
- [Part 1: An image packages the environment, not only the code](#part-1-an-image-packages-the-environment-not-only-the-code)
- [Part 2: You build once and run the same image anywhere](#part-2-you-build-once-and-run-the-same-image-anywhere)
  - [What your project needs](#what-your-project-needs)
  - [Build an image](#build-an-image)
  - [Run a container](#run-a-container)
  - [Override the command](#override-the-command)
- [Part 3: A container should have only the power it needs](#part-3-a-container-should-have-only-the-power-it-needs)
- [Resources](#resources)
- [Part 4: Every line of the Dockerfile buys speed, reproducibility, or safety](#part-4-every-line-of-the-dockerfile-buys-speed-reproducibility-or-safety)
  - [The syntax directive](#the-syntax-directive)
  - [Build arguments](#build-arguments)
  - [Builder stage: install dependencies into a local venv](#builder-stage-install-dependencies-into-a-local-venv)
  - [Private dependencies](#private-dependencies)
  - [Runtime stage: minimal image, non-root user](#runtime-stage-minimal-image-non-root-user)
- [Part 5: The image you tested is the image you ship](#part-5-the-image-you-tested-is-the-image-you-ship)
  - [Tags and promotion](#tags-and-promotion)
  - [Security and supply chain](#security-and-supply-chain)
- [Part 6: State belongs outside the container](#part-6-state-belongs-outside-the-container)
  - [Model and artifact caching](#model-and-artifact-caching)
  - [Datasets and inputs](#datasets-and-inputs)
  - [GPUs](#gpus)
- [Part 7: Logs and debugging happen from the outside](#part-7-logs-and-debugging-happen-from-the-outside)
  - [Follow logs](#follow-logs)
  - [Debug a running container](#debug-a-running-container)
  - [Inspect from outside](#inspect-from-outside)
  - [Logging conventions](#logging-conventions)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)

---

## Key concepts

**Image vs container**: an image is the immutable artifact you build. A container is a running instance of that image. You can start many containers from one image.

**Layers and cache**: each Dockerfile instruction produces a layer. If a layer's inputs do not change, Docker can reuse the cached layer to speed up rebuilds.

**Multi-stage builds**: build dependencies in a "builder" stage, then copy only what you need into a minimal "runtime" stage. This reduces image size and attack surface.

**Volumes**: managed storage that outlives containers. Use them for data you must keep, such as databases, model artifacts you cache intentionally, or local dev state. The container filesystem is disposable by default, so avoid writing important data there.

**Build context**: the directory you pass to `docker build` (the final `.` in the commands below). Instructions like `COPY` can only see files inside it.

**Build argument**: a value passed with `--build-arg` that changes how the image is built, without editing the Dockerfile.

**BuildKit**: Docker's builder. It powers features like `RUN --mount=...`, which the reference Dockerfile relies on.

**Tag vs digest**: a tag such as `python:3.14-slim` is a name that can move to a new image. A digest (`@sha256:<digest>`) identifies one exact image and never moves.

---

## Part 1: An image packages the environment, not only the code

Copying `churn-api`'s source code to a second machine is not enough. The code runs on top of a Python interpreter, a set of libraries at specific versions, and some system packages. Change any of those, and the same code can behave differently.

So the fix is to ship the environment with the code. An image contains all of it: the base system, the interpreter, the installed dependencies, and your application. An image does not change after you build it. The artifact you tested in CI is the artifact you run in production.

An analogy: an image is a sealed meal kit with every ingredient measured out. A container is one meal cooked from it. You can cook as many as you like, and they all taste the same, because nobody goes shopping in between.

That artifact moves through three contexts:

- **Local dev**: use Compose for fast iteration with consistent flags (see [Docker Compose: orchestrate local development]({{ site.baseurl }}/docs/containerization/docker-compose/page/)).
- **CI/CD**: build a deterministic artifact, attach metadata, scan, and publish.
- **Runtime**: run with a production-like posture (least privilege, explicit writable paths).

This page comes with a reference Dockerfile at `_pages/docs/containerization/docker/Dockerfile.example`. It uses a lockfile-driven install, a multi-stage build, a non-root runtime, and optional read-only runtime flags. Those choices serve three goals:

- **Reproducibility**: install dependencies from a lock file.
- **Fast rebuilds**: cache dependency downloads.
- **Security**: run as a non-root user in the runtime image.

What an image does not tell you: whether the code inside it is correct. It guarantees the same behavior everywhere, including the same bugs.

**An image freezes the code and its whole environment, so "what is running?" always has one exact answer.**

---

## Part 2: You build once and run the same image anywhere

We now build an image for `churn-api` and start it. First, the project has to look the way the reference Dockerfile expects.

### What your project needs

The reference Dockerfile expects a typical Python project layout at the project root:

- `pyproject.toml`
- a dependency lock file (for `uv`, this is `uv.lock`)
- a Python package directory, controlled via the `PACKAGE_NAME` build argument
- `main.py` as the entrypoint

For `churn-api`, the package directory is `churn/`, so `PACKAGE_NAME=churn`. If your project differs, adapt `PACKAGE_NAME` and/or the container `CMD` (see [Override the command](#override-the-command)).

The Dockerfile uses BuildKit mounts (`RUN --mount=...`). BuildKit is the default builder since Docker Engine 23.0. On older engines, prefix builds with `DOCKER_BUILDKIT=1`.

Add a `.dockerignore` at the project root as well. Without one, Docker sends your whole directory to the builder, including virtual environments, caches and local artifacts. That makes builds slow and can leak files into images. An example is provided at `_pages/docs/containerization/docker/.dockerignore.example`.

**The Dockerfile expects a lock file, a package directory, and an entrypoint at the project root, plus a `.dockerignore` to keep everything else out.**

### Build an image

Here is the build command. Run it from the project root:

```bash
docker build \
  -f _pages/docs/containerization/docker/Dockerfile.example \
  -t <image>:<tag> \
  --build-arg PACKAGE_NAME=<package_dir> \
  .
```

Why the project root? Because the trailing `.` is the build context. The build needs `pyproject.toml`, your lock file, and your package directory, and it can only see files inside the context.

The `PACKAGE_NAME` build argument must match the folder you want to copy into the image: your top-level Python package directory. Get it wrong and the `COPY` step has nothing to copy.

This is the command you use when you want a deterministic artifact for CI and deployment. Enterprise workflows typically run security controls immediately after the build (policy checks, vulnerability scan, SBOM generation), then publish the image to a registry. [Part 5](#part-5-the-image-you-tested-is-the-image-you-ship) covers that part.

You can tune the build with optional build arguments:

- `--build-arg PYTHON_VERSION=3.14`
- `--build-arg UV_IMAGE=ghcr.io/astral-sh/uv:0.13.9` (pinned for reproducibility; bump deliberately)
- `--build-arg UID=90001`
- `--build-arg PORT=8080`

**Build from the project root, because the build can only see what is inside its context.**

### Run a container

You have an image. Does it start? Here is the quickest way to find out, without Compose:

```bash
docker run --rm \
  -p 8080:8080 \
  -e ENVIRONMENT=prod \
  -e LOG_LEVEL=INFO \
  -e PORT=8080 \
  <image>:<tag>
```

`--rm` removes the container when it exits. `-p 8080:8080` maps a host port to a container port (`-p host:container`). Each `-e` sets an environment variable.

A common confusion: if `-p 8081:8080` is the mapping, which number goes in your browser? The left one. `localhost:8081` on your machine reaches port 8080 inside the container, which is where `churn-api` listens.

**`docker run` turns the image into a running container, and the `-e` flags configure it without a rebuild.**

### Override the command

The reference image uses a virtual environment at `/app/.venv` and runs `main.py`. Sometimes you want a different entrypoint: a dev server, a batch job, or a troubleshooting session. For `churn-api`, that might be the nightly batch scoring module instead of the API. You can override the command at runtime:

```bash
docker run --rm <image>:<tag> /app/.venv/bin/python -m <module_or_package>
```

Anything after the image name replaces the default `CMD`.

**One image can run several entrypoints; whatever follows the image name replaces the default command.**

---

## Part 3: A container should have only the power it needs

The run in Part 2 works, but the container still has more power than it needs. If someone finds a bug in `churn-api` and runs code through it, that code can write anywhere in the container, use every Linux capability the default grants, and try to escalate privileges.

The fix is to take those powers away, one flag at a time. For a production-like posture, add hardened runtime defaults:

```bash
docker run --rm \
  --init \
  --read-only \
  --cap-drop=ALL \
  --security-opt=no-new-privileges \
  --tmpfs /tmp:rw,nosuid,nodev,noexec,size=256m \
  -p 8080:8080 \
  -e HOME=/tmp \
  -e XDG_CACHE_HOME=/tmp/.cache \
  -e XDG_CONFIG_HOME=/tmp/.config \
  -e ENVIRONMENT=prod \
  -e LOG_LEVEL=INFO \
  -e PORT=8080 \
  <image>:<tag>
```

Each new flag takes something away:

- `--init` runs a minimal init process as PID 1, for clean signal handling.
- `--read-only` makes the container filesystem read-only.
- `--cap-drop=ALL` drops all Linux capabilities.
- `--security-opt=no-new-privileges` prevents privilege escalation.
- `--tmpfs /tmp:...` creates one explicit writable path, `/tmp`, in memory.

You might expect `--read-only` alone to be enough, since the app does not write files on purpose. Try it, and many Python services crash at startup. Here is why. Many Python libraries write caches and config under your home directory without telling you. With a read-only filesystem, those writes fail.

That surprise explains the three environment variables. `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME` point those hidden writes at `/tmp`, the one place that is writable.

What hardening does not tell you: that the application itself is secure. It limits the damage of a bug; it does not remove the bug.

**Start from no permissions, then grant one explicit writable path, so a compromised process can do as little as possible.**

---

## Resources

Use these templates when you want a baseline quickly, then customize them for your application.

<details class="boz-resource">
  <summary><code>.dockerignore.example</code></summary>

{% highlight text %}
{% include_relative .dockerignore.example %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>Dockerfile.example</code></summary>

{% highlight dockerfile %}
{% include_relative Dockerfile.example %}
{% endhighlight %}
</details>

---

## Part 4: Every line of the Dockerfile buys speed, reproducibility, or safety

You can use the reference Dockerfile without reading it. But each line is there for a reason, and knowing the reasons helps when you adapt it. We walk through it from the top.

### The syntax directive

```dockerfile
# syntax=docker/dockerfile:1
```

The first line looks like a comment, but it is a parser directive. It tells Docker to use the latest stable 1.x Dockerfile frontend. That way, modern features like `--mount=type=cache` are available and behave consistently, whatever the default Docker engine version on the host.

**The syntax directive makes modern Dockerfile features behave the same on every host.**

### Build arguments

Build arguments let you reuse the same Dockerfile across environments and projects. Here they are:

```dockerfile
ARG PYTHON_VERSION=3.14
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.9
ARG UID=90001
ARG PORT=8080
ARG PACKAGE_NAME=myapp
ARG BUILD_DATE=""
ARG VCS_REF=""
ARG VCS_URL=""
```

Each one controls a single thing:

- **Python base image pin**: `PYTHON_VERSION`
- **Tooling image pin**: `UV_IMAGE` (set this to a version tag or digest in CI for repeatability)
- **Runtime user id**: `UID`
- **Container port**: `PORT` (used in the `EXPOSE` directive)
- **Which package directory to copy**: `PACKAGE_NAME`
- **Image build timestamp (traceability)**: `BUILD_DATE` (used for `org.opencontainers.image.created`)
- **Source revision (traceability)**: `VCS_REF` (used for `org.opencontainers.image.revision`). `VCS` stands for Version Control System (commonly Git).
- **Source repository URL (traceability)**: `VCS_URL` (used for `org.opencontainers.image.source`)

Reach for them whenever you need portability without duplicating Dockerfiles. For example, CI can build the same project with a different Python minor version.

The last three arguments are empty by default. In enterprise CI, they are typically populated from the pipeline context, so every published image links back to an exact commit and repository:

```bash
docker build \
  -f _pages/docs/containerization/docker/Dockerfile.example \
  -t <image>:<tag> \
  --build-arg PACKAGE_NAME=<package_dir> \
  --build-arg UV_IMAGE="ghcr.io/astral-sh/uv:<version-or-digest>" \
  --build-arg BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  --build-arg VCS_URL="$(git remote get-url origin)" \
  .
```

**Build arguments let one Dockerfile serve many builds, and the traceability ones tie each image to its commit.**

### Builder stage: install dependencies into a local venv

Picture the usual edit loop. You change one line in `churn/api.py` and rebuild. Say installing the dependencies takes 90 seconds and copying your code takes 2. If every rebuild reinstalls dependencies, each one-line edit costs 92 seconds. If the dependency layer stays cached, the same edit costs about 2 seconds. Over twenty edits a day, that is half an hour against under a minute.

What decides which case you get? Layer order. Docker rebuilds a layer when its inputs change, and then every layer after it. So the layer that installs dependencies must come before the layer that copies code, and it must see only the files that define dependencies. The builder stage is designed exactly that way:

```dockerfile
FROM ${UV_IMAGE} AS uv
FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=uv /uv /uvx /bin/

ARG PACKAGE_NAME

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# uv: copy from the cache mount instead of hardlinking, and never download
# a managed Python — the venv must use the base image interpreter.
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
```

This stage enforces a reproducibility contract. Dependency installation is locked. The layer inputs are intentionally narrow, so application code changes do not invalidate the dependency cache.

The `PYTHONDONTWRITEBYTECODE` and `PYTHONUNBUFFERED` settings make container behavior more predictable. Python writes no `.pyc` files during execution, and logs are emitted immediately. That second part matters on platforms that collect stdout/stderr.

The two kinds of mount do different jobs:

- `--mount=type=cache,target=/root/.cache/uv` keeps the dependency download cache across builds. Rebuilds reuse already-downloaded wheels and artifacts instead of fetching them again. This is one of the biggest practical speedups in CI and on developer machines.
- `--mount=type=bind,source=...` makes only the dependency inputs (`pyproject.toml` and the lock file) available to that layer. The layer's inputs stay small, so changes to application code do not invalidate the dependency-install layer.

The command `uv sync --locked --no-install-project` reinforces the same intent: install only third-party dependencies first. Once that layer is cached, code edits rebuild quickly. Docker reuses the dependency layer and only redoes the later "copy code + install project" step.

Here is that later step. The Dockerfile copies the project files and installs the project itself:

```dockerfile
COPY pyproject.toml uv.lock ./
COPY ${PACKAGE_NAME} ./${PACKAGE_NAME}
COPY main.py ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable
```

This makes the "what changes invalidate which layers" trade-off explicit. Copying only the dependency metadata and the selected package directory keeps the cache stable and makes the image's runtime surface area reviewable. The final sync is very fast: `uv` sees that the third-party dependencies are already in `.venv`, so it only installs the application code.

What the cache does not tell you: whether a cached layer is still what you want. If you change the lock file, the layer rebuilds. If you only change a version range in your head, nothing rebuilds until the lock file changes.

**Install dependencies from narrow inputs first and copy code last, so a code edit never reinstalls the world.**

### Private dependencies

Some projects install from a private Python index or a private Git repository. The install step then needs credentials. The rule: keep credentials out of the image and mount them only for the install step.

For **private Python indexes**, pass a BuildKit secret and mount it for the `RUN` step that installs dependencies:

```bash
docker build \
  -f _pages/docs/containerization/docker/Dockerfile.example \
  -t <image>:<tag> \
  --build-arg PACKAGE_NAME=<package_dir> \
  --secret id=pip_conf,src=./pip.conf \
  .
```

```dockerfile
RUN --mount=type=secret,id=pip_conf,target=/etc/pip.conf \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
```

For **private Git dependencies over SSH**, forward an SSH agent and mount it only for the install step:

```bash
docker build \
  -f _pages/docs/containerization/docker/Dockerfile.example \
  -t <image>:<tag> \
  --build-arg PACKAGE_NAME=<package_dir> \
  --ssh default \
  .
```

```dockerfile
RUN --mount=type=ssh \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable
```

Why not pass the token as a build argument? It looks harmless, because you never write it to a file. But `ARG` and `ENV` values are recorded in the image. Anything baked into a layer travels with the image to every place you push it. So avoid passing secrets via `ARG`/`ENV` or copying credential files into the image.

**Mount credentials for the one step that needs them, so they never become part of a layer.**

### Runtime stage: minimal image, non-root user

The builder stage is full of tools you need once and never again. The runtime stage leaves them behind:

```dockerfile
FROM python:${PYTHON_VERSION}-slim

ARG UID
ARG PORT
ARG BUILD_DATE
ARG VCS_REF
ARG VCS_URL
ARG PACKAGE_NAME

LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.source="${VCS_URL}"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/nonexistent" \
    --shell "/sbin/nologin" \
    --no-create-home \
    --uid "${UID}" \
    appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/${PACKAGE_NAME} /app/${PACKAGE_NAME}
COPY --from=builder --chown=appuser:appuser /app/main.py /app/main.py

USER appuser
```

The stage starts from a fresh base image, so build-only artifacts do not leak into production.

You might wonder why the `ARG` lines appear again. Build arguments declared before the first `FROM` are outside the build stage scope. They must be re-declared here to be used in `LABEL`s or `ENV`s.

The `LABEL`s are OCI annotations. They attach traceability metadata, like the commit SHA and build date, directly to the final image.

The `PYTHONDONTWRITEBYTECODE` and `PYTHONUNBUFFERED` variables are repeated for a similar reason. Environment variables from the builder stage do not carry over to the new base image.

Next, the stage creates a non-privileged user, `appuser`, and later runs the application as that user. This is a baseline security best practice. If something goes wrong inside the app, it should not have root privileges.

Only the minimum runtime artifacts come over from the builder stage: the prebuilt environment and the application code. Then the stage drops privileges. The copies are ownership-aware (`--chown=...`), so the runtime user can read and write where needed without permission surprises.

Finally, the Dockerfile defines environment defaults and the runtime command:

```dockerfile
ENV ENVIRONMENT=dev
ENV LOG_LEVEL=INFO

# Optional: Add a healthcheck if your application is a web service
# (Note: curl is not installed in python:slim by default, so you may need to apt-get install it, 
# or use a python-based healthcheck)
# HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:${PORT}/health || exit 1

EXPOSE ${PORT}
CMD ["/app/.venv/bin/python", "main.py"]
```

Environment defaults make the container self-describing and straightforward to configure in different environments. The `ENV` lines define sensible defaults you can override at runtime with `-e`. `EXPOSE ${PORT}` documents the expected container port (8080 by default). It does not publish the port; `-p` does that. The venv-based `CMD` ensures the locked environment is the one being executed.

**The runtime stage carries only the environment and the code, and runs them as a user who cannot do much harm.**

**So far:** an image freezes `churn-api` and its environment. We build it from the project root, run it with as little power as possible, and the Dockerfile orders its layers for fast rebuilds, keeps secrets out of layers, and ships a small, non-root runtime. Next, we get that image safely from CI into production.

---

## Part 5: The image you tested is the image you ship

### Tags and promotion

Imagine a bug report: "staging broke on Tuesday". Which `churn-api` image was running? If your only tag is `latest`, you cannot tell, because `latest` has pointed at three different images this week.

The fix is two kinds of tag, each answering one question:

- **Immutable tag**: commit SHA (for example `sha-<git-sha>`)
- **Moving pointers**: `dev`, `staging`, `prod` (or semver release tags)

The SHA tag says exactly what an image is. The moving pointers say where it is deployed. Think of a library book: the ISBN never changes, while the shelf label "new arrivals" moves from book to book.

A pipeline then runs these stages:

1. **Build** from the repo root (so `pyproject.toml` and the lock are in the build context).
2. **Attach metadata** (timestamp, commit SHA, repo URL; see [build arguments](#build-arguments)).
3. **Scan / SBOM / policy checks**.
4. **Push** the immutable SHA tag.
5. **Promote** by retagging only after validation.

Why retag instead of rebuilding for production? A rebuild can pull a newer base image or a newer tool, so it produces a different image than the one you validated. Promotion retags; it never rebuilds. The image you run in staging/prod should be the same digest you built and validated in CI.

In enterprise environments, also consider:

- Pin base images by digest for repeatable builds (for example `python:3.14-slim@sha256:<digest>`).
- Pin tooling images by digest (the reference exposes `UV_IMAGE` so you can set it to a version tag or digest in CI).
- Run a vulnerability scan and produce an SBOM in CI, then sign images before publishing.

**Tag every image with its commit SHA, and promote by moving a pointer to that exact digest.**

### Security and supply chain

Modern container deployments treat security as part of the build pipeline. At a minimum, a CI/CD workflow should automate three checks before an image is pushed to production:

- **Vulnerability scanning**: check the image layers and installed packages for known Common Vulnerabilities and Exposures (CVEs). Tools like [Trivy](https://trivy.dev/) or [Grype](https://github.com/anchore/grype) can fail the build if critical or fixable vulnerabilities are found.
- **SBOM (Software Bill of Materials) generation**: create a machine-readable inventory of all software components, libraries, and transitive dependencies inside your image. This is critical for compliance and incident response, for example to find out quickly whether a new zero-day vulnerability affects you. [Syft](https://github.com/anchore/syft) and Trivy are industry standards for this.
- **Image signing**: cryptographically sign the image digest so your deployment environment (like Kubernetes) can verify the image has not been tampered with since it was built in CI. [Cosign](https://github.com/sigstore/cosign) (part of the Sigstore project) is the leading tool for keyless container signing.

What a clean scan does not tell you: that the image is safe. It tells you that no known vulnerability matched today. New CVEs appear after you ship, which is why the SBOM matters.

**Scan, inventory, and sign each image in CI, so you can prove what it contains and that nobody changed it.**

---

## Part 6: State belongs outside the container

A few situations show up constantly in real systems. Each one tempts you to keep state somewhere hidden inside the container. Making the choice explicit avoids "mystery state" and inconsistent runs.

### Model and artifact caching

Say `churn-api` downloads a model at startup. Where does that file live? Decide deliberately:

- **Ephemeral cache** (safe default): write to `/tmp` and accept that containers are disposable.
- **Named volume cache** (intentional performance trade-off): mount a named volume so repeated starts are faster, then document cache invalidation.

When you enable `--read-only` / `read_only: true`, also route caches to writable paths (commonly under `/tmp`) via environment variables such as `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME`.

**Choose between a disposable cache and a documented volume; never let a cache appear by accident.**

### Datasets and inputs

Treat input data as an external dependency, like a database you connect to:

- **Local dev**: bind-mount a read-only dataset directory, so you do not accidentally write into it.
- **CI and prod**: pull inputs from object storage or a data platform, not from inside the image.

Avoid copying datasets into images. It makes builds slow, images huge, and data lifecycle management unclear.

**Data enters a container at run time, from outside, never at build time.**

### GPUs

If you need GPUs, keep the container contract simple. Make GPU usage **optional**: the same image should run CPU-only.

Prefer runtime configuration (for example `--gpus all`) over building separate "gpu" images. Build a separate image only when you need different system dependencies.

**Turn GPUs on at run time, so one image works on every machine.**

---

## Part 7: Logs and debugging happen from the outside

Containers are most pleasant to operate when you treat them as stateless processes. You capture all logs and signals from the outside, and you go inside only to look.

### Follow logs

Stream logs continuously from a running container:

```bash
docker logs -f <container-name-or-id>
```

**`docker logs -f` is your first stop when a container misbehaves.**

### Debug a running container

Shell into a running container to inspect the filesystem, check environment variables, or run one-off commands:

```bash
docker exec -it <container> /bin/sh
```

Once inside, these checks answer the usual questions:

- **Environment**: `env | sort` (verify variables are set as expected)
- **User**: `id` (confirm the app is running as `appuser`, not root)
- **Filesystem**: `ls -la /app` (check permissions and files copied from the builder stage)
- **Network**: `cat /etc/hosts`, `hostname -i` (verify container networking)

Looking for `ps`? It is not installed in `python:*-slim`. Use `docker top <container>` from the host to list processes.

Anything you change inside a running container disappears when it is replaced. Use `exec` to look, then fix the Dockerfile or the run flags.

**Go inside to diagnose, and fix the cause in the image or the configuration.**

### Inspect from outside

- **What is running**: `docker ps` (add `-a` to include stopped containers)
- **What images exist locally**: `docker images`
- **Resource usage**: `docker stats`
- **Stop a container**: `docker stop <container>`
- **Remove a container**: `docker rm <container>` (add `-f` to force)

**Most questions about a container can be answered from the host without entering it.**

### Logging conventions

- **Write logs to stdout/stderr**: avoid writing app logs to local files inside the container unless you have a clear persistence plan. Containers are simpler to operate when logs go to the platform.
- **Use structured logs when possible**: JSON logs are simpler to parse and ship to centralized logging systems.
- **Promote log level to config**: keep `LOG_LEVEL` (or equivalent) as an environment variable so you can increase verbosity without rebuilding.
- **Add a healthcheck for uptime signals**: a `HEALTHCHECK` makes failures visible to orchestrators and to `docker ps`.
- **Expose metrics and traces explicitly**: if you use Prometheus/OpenTelemetry, document the port and enablement env vars, then publish those ports only where needed.

**Logs go to stdout, verbosity lives in configuration, and health is visible to the platform.**

**So far:** images carry SHA tags and move between environments by retagging, CI scans and signs them, state lives outside the container, and you operate containers from the host, stepping inside only to look.

---

## Common pitfalls

**Building from the wrong directory.** The build context must be the project root. Run `docker build` from a subdirectory and the build cannot find `pyproject.toml`, the lock file, or your package.

**A `PACKAGE_NAME` that does not match your package.** The value must match your top-level Python package directory. Otherwise the `COPY ${PACKAGE_NAME}` step fails.

**Secrets in `ARG` or `ENV`.** They end up in the image. Use `--secret` or `--ssh` and mount credentials only for the install step.

**Datasets copied into the image.** Builds get slow and images get huge. Bind-mount data locally, and pull it from object storage in CI and prod.

**Read-only mode breaks a library.** With `--read-only`, libraries that write to `~/.cache` or `~/.config` fail. Point `HOME`, `XDG_CACHE_HOME` and `XDG_CONFIG_HOME` at `/tmp`.

**Forgetting to re-declare `ARG` after `FROM`.** Arguments declared before the first `FROM` are not visible inside a stage. Re-declare them before using them in `LABEL` or `ENV`.

**A curl healthcheck on a slim image.** `curl` is not installed in `python:slim` by default. Install it, or use a Python-based healthcheck.

**Running a different image than the one you tested.** Rebuilding for production gives you a new image. Promote by retagging the digest you validated in CI.

---

## Recap

- **Keep images small**: multi-stage builds and `python:<version>-slim` reduce size.
- **Prefer lockfiles**: installs should be deterministic and reviewable.
- **Order layers for the cache**: install dependencies before copying application code.
- **Run as non-root**: the reference Dockerfile already does this.
- **Harden runtime permissions**: prefer a read-only filesystem, drop Linux capabilities by default, prevent privilege escalation, and mount `tmpfs` for explicit writable paths (commonly `/tmp` and an app-specific directory).
- **Keep secrets out of layers**: use BuildKit secrets and SSH mounts, not `ARG`/`ENV`.
- **Treat images as release artifacts**: scan for vulnerabilities, generate an SBOM, and sign images before promotion across environments.
- **Tag for traceability**: an immutable SHA tag plus moving environment pointers.
- **Log to stdout/stderr**: let the platform collect logs.
- **Make ports configurable**: use `PORT` and map with `-p host:container`.

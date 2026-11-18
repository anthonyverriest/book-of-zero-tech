---
layout: post
title: "Docker: containerize a Python project"
nav_order: 2
---

You have probably heard "it works on my machine". Maybe you have said it. The code is fine, but your laptop has one Python version, the CI runner has another, and production has a library nobody remembers installing. Docker fixes this by packaging code and dependencies into a single runnable unit. You build it once, and every environment runs that same unit.

This page focuses on building images and running containers. For orchestrating services locally with Docker Compose, see [Docker Compose: orchestrate local development]({{ site.baseurl }}/docs/containerization/docker-compose/page/).

---

## On this page

- [Why containers matter](#why-containers-matter)
- [Key concepts](#key-concepts)
- [Build and run your first image](#build-and-run-your-first-image)
  - [What your project needs](#what-your-project-needs)
  - [Build an image](#build-an-image)
  - [Run a container](#run-a-container)
  - [Override the command](#override-the-command)
- [Resources](#resources)
- [Inside the reference Dockerfile](#inside-the-reference-dockerfile)
  - [The syntax directive](#the-syntax-directive)
  - [Build arguments](#build-arguments)
  - [Builder stage: install dependencies into a local venv](#builder-stage-install-dependencies-into-a-local-venv)
  - [Private dependencies](#private-dependencies)
  - [Runtime stage: minimal image, non-root user](#runtime-stage-minimal-image-non-root-user)
- [Shipping images from CI/CD](#shipping-images-from-cicd)
  - [Tags and promotion](#tags-and-promotion)
  - [Security and supply chain](#security-and-supply-chain)
- [Common patterns](#common-patterns)
  - [Model and artifact caching](#model-and-artifact-caching)
  - [Datasets and inputs](#datasets-and-inputs)
  - [GPUs](#gpus)
- [Logs and debugging](#logs-and-debugging)
  - [Follow logs](#follow-logs)
  - [Debug a running container](#debug-a-running-container)
  - [Inspect from outside](#inspect-from-outside)
  - [Logging conventions](#logging-conventions)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)

---

## Why containers matter

A container answers one question: "what exactly is running?" The answer is an image, and an image does not change after you build it. The artifact you tested in CI is the artifact you run in production.

That artifact moves through three contexts:

- **Local dev**: use Compose for fast iteration with consistent flags (see [Docker Compose: orchestrate local development]({{ site.baseurl }}/docs/containerization/docker-compose/page/)).
- **CI/CD**: build a deterministic artifact, attach metadata, scan, and publish.
- **Runtime**: run with a production-like posture (least privilege, explicit writable paths).

This page comes with a reference Dockerfile at `_pages/docs/containerization/docker/Dockerfile.example`. It uses a lockfile-driven install, a multi-stage build, a non-root runtime, and optional read-only runtime flags. Those choices serve three goals:

- **Reproducibility**: install dependencies from a lock file.
- **Fast rebuilds**: cache dependency downloads.
- **Security**: run as a non-root user in the runtime image.

The result is an image that is reproducible, minimal, and hardened by default. The rest of this page shows how each choice gets you there.

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

## Build and run your first image

### What your project needs

The reference Dockerfile expects a typical Python project layout at the project root:

- `pyproject.toml`
- a dependency lock file (for `uv`, this is `uv.lock`)
- a Python package directory, controlled via the `PACKAGE_NAME` build argument
- `main.py` as the entrypoint

If your project differs, adapt `PACKAGE_NAME` and/or the container `CMD` (see [Override the command](#override-the-command)).

The Dockerfile uses BuildKit mounts (`RUN --mount=...`). BuildKit is the default builder since Docker Engine 23.0. On older engines, prefix builds with `DOCKER_BUILDKIT=1`.

Add a `.dockerignore` at the project root as well. Without one, Docker sends your whole directory to the builder, including virtual environments, caches and local artifacts. That makes builds slow and can leak files into images. An example is provided at `_pages/docs/containerization/docker/.dockerignore.example`.

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

This is the command you use when you want a deterministic artifact for CI and deployment. Enterprise workflows typically run security controls immediately after the build (policy checks, vulnerability scan, SBOM generation), then publish the image to a registry. [Shipping images from CI/CD](#shipping-images-from-cicd) covers that part.

You can tune the build with optional build arguments:

- `--build-arg PYTHON_VERSION=3.14`
- `--build-arg UV_IMAGE=ghcr.io/astral-sh/uv:0.13.9` (pinned for reproducibility; bump deliberately)
- `--build-arg UID=90001`
- `--build-arg PORT=8080`

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

That run works, but the container still has more power than it needs. For a production-like posture, add hardened runtime defaults:

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

Wait, why point `HOME` and the `XDG_*` variables at `/tmp`? Because many Python libraries write caches and config under your home directory. With a read-only filesystem, those writes fail. The variables route them to the one place that is writable.

### Override the command

The reference image uses a virtual environment at `/app/.venv` and runs `main.py`. Sometimes you want a different entrypoint: a dev server, a batch job, or a troubleshooting session. You can override the command at runtime:

```bash
docker run --rm <image>:<tag> /app/.venv/bin/python -m <module_or_package>
```

Anything after the image name replaces the default `CMD`.

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

## Inside the reference Dockerfile

You can use the reference Dockerfile without reading it. But each line is there for a reason, and knowing the reasons helps when you adapt it. Let's walk through it from the top.

### The syntax directive

```dockerfile
# syntax=docker/dockerfile:1
```

The first line looks like a comment, but it is a parser directive. It tells Docker to use the latest stable 1.x Dockerfile frontend. That way, modern features like `--mount=type=cache` are available and behave consistently, whatever the default Docker engine version on the host.

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

### Builder stage: install dependencies into a local venv

Picture the usual edit loop. You change one line of application code and rebuild. If that rebuild reinstalls every dependency, you wait minutes for nothing. The builder stage is designed so that does not happen:

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

Avoid passing secrets via `ARG`/`ENV` or copying credential files into the image. Anything baked into a layer travels with the image to every place you push it.

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

Environment defaults make the container self-describing and straightforward to configure in different environments. The `ENV` lines define sensible defaults you can override at runtime with `-e`. `EXPOSE ${PORT}` documents the expected container port (8080 by default). The venv-based `CMD` ensures the locked environment is the one being executed.

---

## Shipping images from CI/CD

### Tags and promotion

Imagine a bug report: "staging broke on Tuesday". Which image was running? If your only tag is `latest`, you cannot tell. So tag images so every artifact is traceable:

- **Immutable tag**: commit SHA (for example `sha-<git-sha>`)
- **Moving pointers**: `dev`, `staging`, `prod` (or semver release tags)

The SHA tag says exactly what an image is. The moving pointers say where it is deployed.

A pipeline then runs these stages:

1. **Build** from the repo root (so `pyproject.toml` and the lock are in the build context).
2. **Attach metadata** (timestamp, commit SHA, repo URL; see [build arguments](#build-arguments)).
3. **Scan / SBOM / policy checks**.
4. **Push** the immutable SHA tag.
5. **Promote** by retagging only after validation.

Promotion retags; it never rebuilds. The image you run in staging/prod should be the same digest you built and validated in CI.

In enterprise environments, also consider:

- Pin base images by digest for repeatable builds (for example `python:3.14-slim@sha256:<digest>`).
- Pin tooling images by digest (the reference exposes `UV_IMAGE` so you can set it to a version tag or digest in CI).
- Run a vulnerability scan and produce an SBOM in CI, then sign images before publishing.

### Security and supply chain

Modern container deployments treat security as part of the build pipeline. At a minimum, a CI/CD workflow should automate three checks before an image is pushed to production:

- **Vulnerability scanning**: check the image layers and installed packages for known Common Vulnerabilities and Exposures (CVEs). Tools like [Trivy](https://trivy.dev/) or [Grype](https://github.com/anchore/grype) can fail the build if critical or fixable vulnerabilities are found.
- **SBOM (Software Bill of Materials) generation**: create a machine-readable inventory of all software components, libraries, and transitive dependencies inside your image. This is critical for compliance and incident response, for example to find out quickly whether a new zero-day vulnerability affects you. [Syft](https://github.com/anchore/syft) and Trivy are industry standards for this.
- **Image signing**: cryptographically sign the image digest so your deployment environment (like Kubernetes) can verify the image has not been tampered with since it was built in CI. [Cosign](https://github.com/sigstore/cosign) (part of the Sigstore project) is the leading tool for keyless container signing.

---

## Common patterns

A few situations show up constantly in real systems. Each one tempts you to keep state somewhere hidden. Making the choice explicit avoids "mystery state" and inconsistent runs.

### Model and artifact caching

Say your service downloads a model at startup. Where does that file live? Decide deliberately:

- **Ephemeral cache** (safe default): write to `/tmp` and accept that containers are disposable.
- **Named volume cache** (intentional performance trade-off): mount a named volume so repeated starts are faster, then document cache invalidation.

When you enable `--read-only` / `read_only: true`, also route caches to writable paths (commonly under `/tmp`) via environment variables such as `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME`.

### Datasets and inputs

Treat input data as an external dependency, like a database you connect to:

- **Local dev**: bind-mount a read-only dataset directory, so you do not accidentally write into it.
- **CI and prod**: pull inputs from object storage or a data platform, not from inside the image.

Avoid copying datasets into images. It makes builds slow, images huge, and data lifecycle management unclear.

### GPUs

If you need GPUs, keep the container contract simple. Make GPU usage **optional**: the same image should run CPU-only.

Prefer runtime configuration (for example `--gpus all`) over building separate "gpu" images. Build a separate image only when you truly need different system dependencies.

---

## Logs and debugging

Containers are most pleasant to operate when you treat them as stateless processes. You capture all logs and signals from the outside, and you go inside only to look.

### Follow logs

Stream logs continuously from a running container:

```bash
docker logs -f <container-name-or-id>
```

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

### Inspect from outside

- **What is running**: `docker ps` (add `-a` to include stopped containers)
- **What images exist locally**: `docker images`
- **Resource usage**: `docker stats`
- **Stop a container**: `docker stop <container>`
- **Remove a container**: `docker rm <container>` (add `-f` to force)

### Logging conventions

- **Write logs to stdout/stderr**: avoid writing app logs to local files inside the container unless you have a clear persistence plan. Containers are simpler to operate when logs go to the platform.
- **Use structured logs when possible**: JSON logs are simpler to parse and ship to centralized logging systems.
- **Promote log level to config**: keep `LOG_LEVEL` (or equivalent) as an environment variable so you can increase verbosity without rebuilding.
- **Add a healthcheck for uptime signals**: a `HEALTHCHECK` makes failures visible to orchestrators and to `docker ps`.
- **Expose metrics and traces explicitly**: if you use Prometheus/OpenTelemetry, document the port and enablement env vars, then publish those ports only where needed.

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

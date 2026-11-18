---
layout: post
title: "Docker Compose: orchestrate local development"
nav_order: 3
---

If you have read the Docker page, you have seen a `docker run` command with a dozen flags. Typing it once is fine. Typing it fifty times a day, and getting it slightly different each time, is not. Docker Compose writes those flags down in a file. Then a single command builds, starts, and wires together the services that make up your local development stack.

This page covers the Compose workflow and configuration. For building images and running standalone containers, see [Docker: containerize a Python project]({{ site.baseurl }}/docs/containerization/docker/page/).

---

## On this page

- [Why Compose matters](#why-compose-matters)
- [Key concepts](#key-concepts)
- [Your first stack](#your-first-stack)
  - [Setup steps](#setup-steps)
  - [The .env file](#the-env-file)
- [Resources](#resources)
- [The day-to-day loop](#the-day-to-day-loop)
- [The hardened posture](#the-hardened-posture)
- [What each Compose field does](#what-each-compose-field-does)
  - [Build and configuration](#build-and-configuration)
  - [Networking and storage](#networking-and-storage)
  - [Restart policies](#restart-policies)
  - [Commands and names](#commands-and-names)
  - [Runtime hardening](#runtime-hardening)
  - [Healthchecks](#healthchecks)
- [Logs and debugging](#logs-and-debugging)
  - [Follow logs](#follow-logs)
  - [Debug a running service](#debug-a-running-service)
  - [Inspect from outside](#inspect-from-outside)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)

---

## Why Compose matters

Local development needs consistency. Everyone on the team should start the app with the same flags, the same ports, and the same environment. A compose file is that agreement, checked into the repository.

This page comes with two compose files. The first is a baseline at `_pages/docs/containerization/docker-compose/docker-compose.example.yaml`, a starting point for running the container locally.

The second is an optional hardened override at `_pages/docs/containerization/docker-compose/docker-compose.hardened.example.yaml`. It layers on top of the baseline. With one additional `-f` flag, you switch from a low-friction dev posture to a production-like posture.

---

## Key concepts

**Services**: a service is a named container definition in `docker-compose.yaml`. Each service maps to one image (built or pulled) and one or more running containers.

**Override files**: Compose merges multiple `-f` files in order. Use an override file (for example `docker-compose.hardened.yaml`) to layer settings on top of a baseline without editing it.

**Variable substitution**: `${VAR:-default}` in a compose file resolves from your shell environment and the project-level `.env` file. If neither sets `VAR`, Compose uses `default`. This keeps the compose file stable across environments.

**`env_file` vs `environment`**: `env_file` loads variables into the running container at runtime. `environment` sets variables directly in the compose file and can override `env_file` values. Neither is used for build-time `args`; those come from variable substitution or the shell.

---

## Your first stack

This page assumes Docker and Docker Compose are installed. If you are new to Docker images, start with the [Docker page]({{ site.baseurl }}/docs/containerization/docker/page/) for image building fundamentals and the reference Dockerfile.

### Setup steps

1. Copy the examples into conventional names at the project root:
   - `_pages/docs/containerization/docker/Dockerfile.example` → `Dockerfile`
   - `_pages/docs/containerization/docker-compose/docker-compose.example.yaml` → `docker-compose.yaml`
   - `_pages/docs/containerization/docker-compose/docker-compose.hardened.example.yaml` → `docker-compose.hardened.yaml`, if you want a production-like posture
2. Create the `.env` file at the project root (see [The .env file](#the-env-file)).
3. Start the service:

```bash
docker compose up --build
```

`--build` rebuilds the image from your local sources before starting. That is it: one command instead of a long `docker run`.

Prefer not to copy files? You can also adapt the compose file to reference the example Dockerfile path directly (set `dockerfile: _pages/docs/containerization/docker/Dockerfile.example`).

### The .env file

Here is a minimal `.env`, shown as two parts:

```text
# .env (compose variable substitution)
PACKAGE_NAME=myapp
PORT=8080
```

```text
# .env (runtime container environment)
ENVIRONMENT=dev
LOG_LEVEL=INFO
```

Why two parts in one file? Because `.env` does two jobs. Compose reads it for `${...}` variable substitution in the compose file, which is how `PACKAGE_NAME` reaches the build. The baseline also passes it into the container at runtime via `env_file`, which is how your application gets its configuration.

Keep runtime secrets out of version control. Treat `.env` as local-only inputs. When you need a documented baseline, share a template such as `.env.example` instead.

---

## Resources

Use these templates when you want a baseline quickly, then customize them for your application.

<details class="boz-resource">
  <summary><code>docker-compose.example.yaml</code></summary>

{% highlight yaml %}
{% include_relative docker-compose.example.yaml %}
{% endhighlight %}
</details>

<details class="boz-resource">
  <summary><code>docker-compose.hardened.example.yaml</code></summary>

{% highlight yaml %}
{% include_relative docker-compose.hardened.example.yaml %}
{% endhighlight %}
</details>

---

## The day-to-day loop

Once the stack runs, your days look like this:

- **Start the stack**: follow the [setup steps](#setup-steps).
- **Observe logs**: use the commands in [Logs and debugging](#logs-and-debugging).
- **Restart after changes** (when you are not bind-mounting code): `docker compose up --build --force-recreate`
- **Run a one-shot command in the same image** (migrations, a backfill, a smoke test): see below.
- **Debug inside the container**: use the shell commands in [Logs and debugging](#logs-and-debugging).

A one-shot command runs in a fresh container from the same image, then goes away:

```bash
docker compose run --rm <service-name> /app/.venv/bin/python -m <module>
```

What about live code reload? If your local workflow needs it, make it an explicit compose variant: bind-mount the code and run a dev server command. Keep the default path "rebuild the image". That way you do not accidentally depend on host-only state, and what you test is what the image contains.

---

## The hardened posture

The baseline is friendly on purpose. Production is not. The hardened override lets you find out early what breaks when the container loses its freedoms:

```bash
docker compose -f docker-compose.yaml -f docker-compose.hardened.yaml up --build
```

Compose merges the two files in order. The override adds `read_only: true`, drops all Linux capabilities, prevents privilege escalation, and creates explicit writable `tmpfs` mounts for `/tmp`.

Use it to surface hidden write assumptions early, while the baseline setup stays low-friction. A common surprise: Python libraries that try to write to `~/.cache` or `~/.config`. Route those caches to writable locations (commonly under `/tmp`) via environment variables such as `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME`.

---

## What each Compose field does

The baseline file uses a handful of fields. Each one has a job, and each one has a case where you should leave it out.

### Build and configuration

- **`build`**: use when you want the image rebuilt from local sources as part of `up`. Avoid it when you want to pin to a prebuilt image digest.
  - **`build.args`**: use when the Dockerfile requires build-time arguments. The reference Dockerfile requires `PACKAGE_NAME` to match your top-level Python package directory. `UV_IMAGE` is optional, if you want to pin the installer image.
  - Compose variable substitution for build args uses your shell environment and the project-level `.env` file. It does not use `env_file`, which only sets runtime container environment variables.
- **`env_file`**: use when you want a single place for environment-specific defaults, and to keep `docker-compose.yaml` stable across environments.
- **`environment`**: use for values you want to be explicit at the compose layer, and to override `env_file` selectively.

### Networking and storage

- **`ports`**: use when the service must be reachable from the host (local testing). Avoid publishing ports you do not need.
  - For a configurable port mapping, use compose variable substitution (for example `"${PORT:-8080}:${PORT:-8080}"`) and set `PORT` at runtime so the app and the healthcheck agree.
- **`volumes`**: use when the container needs persistent data (named volumes), or when you want to mount local files into the container for dev (bind mounts). Prefer explicit mounts over relying on writes to the container filesystem.

### Restart policies

`restart` controls how Docker restarts containers. The right policy depends on whether the container is a job or a service:

- `restart: "no"`: use for one-shot tasks and batch jobs where failure should surface immediately, and exit codes should be visible to CI and operators.
- `restart: on-failure[:N]`: use for transient failures where retrying is reasonable. Consider adding a max retry count.
- `restart: always`: use for long-running services that must restart whenever they exit. After a manual `docker stop`, the container stays stopped until the Docker daemon restarts or you start it again. It is commonly used outside local dev.
- `restart: unless-stopped`: use for long-running services that should restart on failure and on daemon restart, but stay stopped if an operator intentionally stops them. This is common for local dev stacks.

### Commands and names

- **`command`**: use when the runtime command differs between contexts (dev server vs worker vs batch).
- **`container_name`**: use only when you have a strong reason to force a fixed container name. Avoid it if you want to scale services (for example `docker compose up --scale ...`) or if you run multiple copies of the same stack. Two containers cannot share one name, so the fixed name causes collisions.

### Runtime hardening

`init`, `read_only`, `cap_drop`, `security_opt` and `tmpfs` give you runtime hardening defaults: a read-only filesystem, least privilege, and explicit writable paths such as `/tmp`.

- `init: true` enables a minimal init process as PID 1 inside the container. It improves signal handling (shutdown behavior) and reaps zombie processes when your app spawns subprocesses.
- `read_only: true` makes the container filesystem read-only. This detects unexpected writes early and reduces the amount of mutable state a container can accumulate at runtime.
- `cap_drop: [ALL]` removes Linux capabilities from the container to enforce least privilege. Add back only what you can justify for the workload.
- `security_opt: ["no-new-privileges:true"]` prevents privilege escalation through setuid/setcap binaries, even if they exist in the image.
- `tmpfs: [...]` creates explicit writable mounts in memory (for example `/tmp`). Combined with `read_only: true`, this makes writable paths intentional and straightforward to audit.

In practice, keep these settings in a separate override file (for example `docker-compose.hardened.yaml`), so the baseline setup stays low-friction to run.

A hardened setup can surface hidden assumptions in Python libraries that try to write to `~/.cache` or `~/.config`. If you use `read_only: true` and a non-root user, route caches and config to writable locations (commonly under `/tmp`) via environment variables such as `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME`.

### Healthchecks

**`healthcheck`**: use when you want an explicit readiness signal for local orchestration and troubleshooting. Prefer checks that do not require extra OS packages. The example uses Python to probe the listening port, because `curl` is not in the slim base image.

---

## Logs and debugging

With Compose, you rarely want logs from one container at a time. `docker compose logs -f` gives you a unified stream across all services in a stack.

### Follow logs

Stream logs from all services:

```bash
docker compose logs -f
```

Stream logs from a single service:

```bash
docker compose logs -f <service-name>
```

For single-container log streaming, see the [Docker page: Logs and debugging]({{ site.baseurl }}/docs/containerization/docker/page/#logs-and-debugging).

### Debug a running service

Shell into a running service to inspect the filesystem, check environment variables, or run one-off commands:

```bash
docker compose exec <service-name> /bin/sh
```

Run a one-shot command without starting the full stack:

```bash
docker compose run --rm <service-name> <command>
```

Which one do you want? `exec` enters a container that is already running. `run` starts a new one.

### Inspect from outside

- **Compose status**: `docker compose ps`
- **Stop a compose stack**: `docker compose down` (add `-v` if you intentionally want to remove named volumes)
- **Rebuild and restart**: `docker compose up --build --force-recreate`

For standalone Docker commands (`docker ps`, `docker images`, `docker stats`, etc.), see the [Docker page: Logs and debugging]({{ site.baseurl }}/docs/containerization/docker/page/#logs-and-debugging).

---

## Common pitfalls

**Expecting `env_file` to feed build args.** It only sets runtime variables. Build args come from your shell environment and the project-level `.env` file, through variable substitution.

**Committing `.env`.** It holds local inputs and can hold secrets. Commit a `.env.example` template instead.

**Running stale code.** Without a bind mount, the container runs the code baked into the image. After changes, rebuild with `docker compose up --build --force-recreate`.

**Setting `container_name` and then scaling.** A fixed name blocks `docker compose up --scale ...` and collides when you run multiple copies of the same stack.

**Losing data with `down -v`.** The `-v` flag removes named volumes. Add it only when you intend to.

**Wondering why a stopped container came back.** With `restart: always`, a container you stopped manually starts again when the Docker daemon restarts. Use `unless-stopped` if you want it to stay stopped.

**Hardened mode breaks a library.** With `read_only: true`, writes to `~/.cache` or `~/.config` fail. Route them to `/tmp` with `HOME`, `XDG_CACHE_HOME` and `XDG_CONFIG_HOME`.

---

## Recap

- Compose writes your `docker run` flags down, so one command builds and starts the stack: `docker compose up --build`.
- `.env` drives variable substitution and, through `env_file`, the runtime environment. Keep it out of version control.
- Build args come from substitution or the shell, never from `env_file`.
- Layer `docker-compose.hardened.yaml` on top of the baseline with a second `-f` to test a production-like posture.
- Pick the restart policy by workload: `"no"` for jobs, `unless-stopped` for local dev services.
- Avoid `container_name` if you scale or run multiple copies of a stack.
- Use `docker compose logs -f`, `exec` and `run --rm` to observe and debug.

---
layout: post
title: "Docker Compose: orchestrate local development"
nav_order: 3
---

If you have read the Docker page, you have seen a `docker run` command with a dozen flags. Typing it once is fine. Typing it fifty times a day, and getting it slightly different each time, is not. The real question this page answers: how does a whole team start the same local stack, with the same settings, every time?

We reduce it to a smaller one first: how do you stop retyping one long `docker run` command? **Docker Compose** answers it by writing those flags down in a file. Then a single command builds, starts, and wires together the services that make up your local development stack.

We keep the example from the Docker page: `churn-api`, a Python service on port 8080 whose package directory is `churn/`. In five parts, we write its first compose file, settle into a daily loop, switch on a production-like posture, read every field, and debug the stack. For building images and running standalone containers, see [Docker: containerize a Python project]({{ site.baseurl }}/docs/containerization/docker/page/).

---

## On this page

- [Key concepts](#key-concepts)
- [Part 1: A compose file is a `docker run` command you never retype](#part-1-a-compose-file-is-a-docker-run-command-you-never-retype)
  - [Setup steps](#setup-steps)
  - [The .env file](#the-env-file)
- [Resources](#resources)
- [Part 2: The daily loop is rebuild, observe, repeat](#part-2-the-daily-loop-is-rebuild-observe-repeat)
- [Part 3: A second file switches on a production-like posture](#part-3-a-second-file-switches-on-a-production-like-posture)
- [Part 4: Every field has a job, and a case where you leave it out](#part-4-every-field-has-a-job-and-a-case-where-you-leave-it-out)
  - [Build and configuration](#build-and-configuration)
  - [Networking and storage](#networking-and-storage)
  - [Restart policies](#restart-policies)
  - [Commands and names](#commands-and-names)
  - [Runtime hardening](#runtime-hardening)
  - [Healthchecks](#healthchecks)
- [Part 5: One log stream covers the whole stack](#part-5-one-log-stream-covers-the-whole-stack)
  - [Follow logs](#follow-logs)
  - [Debug a running service](#debug-a-running-service)
  - [Inspect from outside](#inspect-from-outside)
- [Common pitfalls](#common-pitfalls)
- [Recap](#recap)
- [Exercise](#exercise)

---

## Key concepts

**Services**: a service is a named container definition in `docker-compose.yaml`. Each service maps to one image (built or pulled) and one or more running containers.

**Override files**: Compose merges multiple `-f` files in order. Use an override file (for example `docker-compose.hardened.yaml`) to layer settings on top of a baseline without editing it.

**Variable substitution**: `${VAR:-default}` in a compose file resolves from your shell environment and the project-level `.env` file. If neither sets `VAR`, Compose uses `default`. This keeps the compose file stable across environments.

**`env_file` vs `environment`**: `env_file` loads variables into the running container at runtime. `environment` sets variables directly in the compose file and can override `env_file` values. Neither is used for build-time `args`; those come from variable substitution or the shell.

---

## Part 1: A compose file is a `docker run` command you never retype

Start with one developer and one command. Ana runs `churn-api` with a port mapping, three environment variables, and a build argument. It works on her machine.

Now add a second developer. Ben copies the command from a chat message, misses one `-e` flag, and his service starts with a different log level. Nobody notices for a week. With five developers, there are five slightly different commands.

Local development needs consistency. Everyone on the team should start the app with the same flags, the same ports, and the same environment. A compose file is that agreement, checked into the repository. Think of it as a recipe card taped inside the kitchen door: nobody cooks from memory any more.

This page comes with two compose files. The first is a baseline at `_pages/docs/containerization/docker-compose/docker-compose.example.yaml`, a starting point for running the container locally. The second is an optional hardened override, covered in [Part 3](#part-3-a-second-file-switches-on-a-production-like-posture).

This page assumes Docker and Docker Compose are installed. If you are new to Docker images, start with the [Docker page]({{ site.baseurl }}/docs/containerization/docker/page/) for image building fundamentals and the reference Dockerfile.

**A compose file turns a long, error-prone command into a reviewed file that everyone runs the same way.**

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

`--build` rebuilds the image from your local sources before starting. One command replaces the long `docker run`.

Prefer not to copy files? You can also adapt the compose file to reference the example Dockerfile path directly (set `dockerfile: _pages/docs/containerization/docker/Dockerfile.example`).

**Three files at the project root, and `docker compose up --build` starts the stack.**

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

For `churn-api`, `PACKAGE_NAME` would be `churn`.

Why two parts in one file? Because `.env` does two jobs. Compose reads it for `${...}` variable substitution in the compose file, which is how `PACKAGE_NAME` reaches the build. The baseline also passes it into the container at runtime via `env_file`, which is how your application gets its configuration.

Follow one variable to see both jobs. In the baseline, the build argument reads `PACKAGE_NAME: ${PACKAGE_NAME:-myapp}`. With `PACKAGE_NAME=churn` in `.env`, Compose substitutes `churn`, and the Dockerfile copies `churn/`. Delete the line, and the default `myapp` wins, which makes the copy step fail on a project without a `myapp/` folder. Which makes sense, because the default is only a fallback, not a guess about your project.

Now a surprise. Set `ENVIRONMENT=prod` in `.env`, start the stack, and the container still reports `dev`. Why? The baseline also sets `ENVIRONMENT: dev` under `environment`, and `environment` overrides `env_file`. The file closer to the service wins.

Keep runtime secrets out of version control. Treat `.env` as local-only inputs. When you need a documented baseline, share a template such as `.env.example` instead.

**`.env` feeds both the compose file and the container, and `environment` in the compose file overrides it.**

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

## Part 2: The daily loop is rebuild, observe, repeat

Once the stack runs, your days look like this:

- **Start the stack**: follow the [setup steps](#setup-steps).
- **Observe logs**: use the commands in [Part 5](#part-5-one-log-stream-covers-the-whole-stack).
- **Restart after changes** (when you are not bind-mounting code): `docker compose up --build --force-recreate`
- **Run a one-shot command in the same image** (migrations, a backfill, a smoke test): see below.
- **Debug inside the container**: use the shell commands in [Part 5](#part-5-one-log-stream-covers-the-whole-stack).

A one-shot command runs in a fresh container from the same image, then goes away. For `churn-api`, that could be a backfill of last week's scores:

```bash
docker compose run --rm <service-name> /app/.venv/bin/python -m <module>
```

A common confusion: you edit `churn/api.py`, refresh the browser, and nothing changed. The container runs the code baked into the image when it was built. Your edit exists only on the host until you rebuild.

What about live code reload? If your local workflow needs it, make it an explicit compose variant: bind-mount the code and run a dev server command. Keep the default path "rebuild the image". That way you do not accidentally depend on host-only state, and what you test is what the image contains.

**By default, a code change reaches the container only through a rebuild, so what you test is what the image holds.**

**So far:** a checked-in compose file replaces the long `docker run`, `.env` feeds both substitution and runtime configuration, and the daily loop is rebuild, observe, and run one-shot commands in the same image.

---

## Part 3: A second file switches on a production-like posture

The baseline is friendly on purpose. Production is not. If `churn-api` quietly writes a cache file into the container, the baseline lets it, and you discover the problem only when production runs read-only.

You could edit the baseline to add hardening, but then every developer pays the friction on every run. The fix is a second file that layers on top. The hardened override at `_pages/docs/containerization/docker-compose/docker-compose.hardened.example.yaml` changes nothing in the baseline; it adds settings:

```bash
docker compose -f docker-compose.yaml -f docker-compose.hardened.yaml up --build
```

Compose merges the two files in order. The override adds `read_only: true`, drops all Linux capabilities, prevents privilege escalation, and creates explicit writable `tmpfs` mounts for `/tmp`. Later files win where both set the same field, the way a transparent sheet laid over a drawing adds lines without erasing the original.

Use it to surface hidden write assumptions early, while the baseline setup stays low-friction. A common surprise: Python libraries that try to write to `~/.cache` or `~/.config`. The override already routes those caches to writable locations under `/tmp` via `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME`.

What the hardened run does not tell you: that production is configured the same way. It is a rehearsal of the restrictions, not a copy of your production platform.

**Layer the hardened override with a second `-f` to find hidden writes on your laptop instead of in production.**

---

## Part 4: Every field has a job, and a case where you leave it out

The baseline file uses a handful of fields. Each one has a job, and each one has a case where you should leave it out.

### Build and configuration

- **`build`**: use when you want the image rebuilt from local sources as part of `up`. Avoid it when you want to pin to a prebuilt image digest.
  - **`build.args`**: use when the Dockerfile requires build-time arguments. The reference Dockerfile requires `PACKAGE_NAME` to match your top-level Python package directory. `UV_IMAGE` is optional, if you want to pin the installer image.
  - Compose variable substitution for build args uses your shell environment and the project-level `.env` file. It does not use `env_file`, which only sets runtime container environment variables.
- **`env_file`**: use when you want a single place for environment-specific defaults, and to keep `docker-compose.yaml` stable across environments.
- **`environment`**: use for values you want to be explicit at the compose layer, and to override `env_file` selectively.

Why can `env_file` not feed a build argument? Timing. Build arguments are needed while the image is built, and `env_file` is read only when a container starts from that image. By then the build is over.

**Build inputs come from substitution; runtime configuration comes from `env_file` and `environment`.**

### Networking and storage

- **`ports`**: use when the service must be reachable from the host (local testing). Avoid publishing ports you do not need.
  - For a configurable port mapping, use compose variable substitution (for example `"${PORT:-8080}:${PORT:-8080}"`) and set `PORT` at runtime so the app and the healthcheck agree.
- **`volumes`**: use when the container needs persistent data (named volumes), or when you want to mount local files into the container for dev (bind mounts). Prefer explicit mounts over relying on writes to the container filesystem.

**Publish only the ports you use, and keep every piece of persistent data in an explicit mount.**

### Restart policies

`restart` controls how Docker restarts containers. The right policy depends on whether the container is a job or a service:

- `restart: "no"`: use for one-shot tasks and batch jobs where failure should surface immediately, and exit codes should be visible to CI and operators.
- `restart: on-failure[:N]`: use for transient failures where retrying is reasonable. Consider adding a max retry count.
- `restart: always`: use for long-running services that must restart whenever they exit. After a manual `docker stop`, the container stays stopped until the Docker daemon restarts or you start it again. It is commonly used outside local dev.
- `restart: unless-stopped`: use for long-running services that should restart on failure and on daemon restart, but stay stopped if an operator intentionally stops them. This is common for local dev stacks.

The difference between the last two shows up after a reboot. You stop `churn-api` on Friday and restart your laptop on Monday. With `always`, it comes back. With `unless-stopped`, it stays stopped, because you stopped it on purpose.

**Jobs should fail loudly with `"no"`; local services usually want `unless-stopped`.**

### Commands and names

- **`command`**: use when the runtime command differs between contexts (dev server vs worker vs batch).
- **`container_name`**: use only when you have a strong reason to force a fixed container name. Avoid it if you want to scale services (for example `docker compose up --scale ...`) or if you run multiple copies of the same stack. Two containers cannot share one name, so the fixed name causes collisions.

**Leave container names to Compose unless a fixed name is worth giving up scaling.**

### Runtime hardening

`init`, `read_only`, `cap_drop`, `security_opt` and `tmpfs` give you runtime hardening defaults: a read-only filesystem, least privilege, and explicit writable paths such as `/tmp`.

- `init: true` enables a minimal init process as PID 1 inside the container. It improves signal handling (shutdown behavior) and reaps zombie processes when your app spawns subprocesses.
- `read_only: true` makes the container filesystem read-only. This detects unexpected writes early and reduces the amount of mutable state a container can accumulate at runtime.
- `cap_drop: [ALL]` removes Linux capabilities from the container to enforce least privilege. Add back only what you can justify for the workload.
- `security_opt: ["no-new-privileges:true"]` prevents privilege escalation through setuid/setcap binaries, even if they exist in the image.
- `tmpfs: [...]` creates explicit writable mounts in memory (for example `/tmp`). Combined with `read_only: true`, this makes writable paths intentional and straightforward to audit.

In practice, keep these settings in a separate override file (for example `docker-compose.hardened.yaml`), so the baseline setup stays low-friction to run. The baseline keeps only `init: true`.

If you use `read_only: true` and a non-root user, route caches and config to writable locations (commonly under `/tmp`) via environment variables such as `HOME`, `XDG_CACHE_HOME`, and `XDG_CONFIG_HOME`.

**Hardening fields remove freedoms the app should not need, and `tmpfs` gives back the one writable path it does.**

### Healthchecks

**`healthcheck`**: use when you want an explicit readiness signal for local orchestration and troubleshooting. Prefer checks that do not require extra OS packages. The example uses Python to probe the listening port, because `curl` is not in the slim base image.

What a passing healthcheck does not tell you: that `churn-api` returns correct predictions. The example check confirms that something accepts connections on the port, nothing more.

**A healthcheck tells Compose the service is reachable, not that it is right.**

**So far:** the baseline file is a reviewed `docker run`, the hardened override adds restrictions without touching it, and each field has a job: build inputs through substitution, runtime configuration through `env_file` and `environment`, a restart policy matched to the workload, and a healthcheck that needs no extra packages.

---

## Part 5: One log stream covers the whole stack

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

For single-container log streaming, see the [Docker page: Logs and debugging]({{ site.baseurl }}/docs/containerization/docker/page/#part-7-logs-and-debugging-happen-from-the-outside).

**Use the stack-wide stream first, then narrow it to one service.**

### Debug a running service

Shell into a running service to inspect the filesystem, check environment variables, or run one-off commands:

```bash
docker compose exec <service-name> /bin/sh
```

Run a one-shot command without starting the full stack:

```bash
docker compose run --rm <service-name> <command>
```

Which one do you want? `exec` enters a container that is already running. `run` starts a new one. So `exec` shows you the state of the `churn-api` that misbehaves right now, while `run` gives you a clean copy to try something in.

**`exec` inspects the live container; `run --rm` tests in a fresh one.**

### Inspect from outside

- **Compose status**: `docker compose ps`
- **Stop a compose stack**: `docker compose down` (add `-v` if you intentionally want to remove named volumes)
- **Rebuild and restart**: `docker compose up --build --force-recreate`

For standalone Docker commands (`docker ps`, `docker images`, `docker stats`, etc.), see the [Docker page: Logs and debugging]({{ site.baseurl }}/docs/containerization/docker/page/#part-7-logs-and-debugging-happen-from-the-outside).

**`ps`, `down`, and `up --build --force-recreate` cover the stack's whole lifecycle.**

---

## Common pitfalls

**Expecting `env_file` to feed build args.** It only sets runtime variables. Build args come from your shell environment and the project-level `.env` file, through variable substitution.

**A `.env` value that seems ignored.** A key set under `environment` in the compose file overrides the same key from `env_file`.

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
- Build args come from substitution or the shell, never from `env_file`, and `environment` overrides `env_file`.
- Layer `docker-compose.hardened.yaml` on top of the baseline with a second `-f` to test a production-like posture.
- Pick the restart policy by workload: `"no"` for jobs, `unless-stopped` for local dev services.
- Avoid `container_name` if you scale or run multiple copies of a stack.
- Use `docker compose logs -f`, `exec` and `run --rm` to observe and debug.

---

## Exercise

Set up the baseline stack with `LOG_LEVEL=DEBUG` and `ENVIRONMENT=prod` in `.env`. Start it, then run `docker compose exec <service-name> env | sort`. Which of the two values reached the container, and which one did the compose file override? Then start the stack again with the hardened override added, and check with `docker compose exec <service-name> id` and a write to `/app` whether the restrictions took effect.

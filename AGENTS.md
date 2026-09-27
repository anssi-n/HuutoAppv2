# AGENTS.md

## Project
HuutoApp: huuto.net listing automation. Two processes share Postgres + a Redis list queue:
- **API**: FastAPI app in `main.py` (run: `uv run uvicorn main:app --port 8000`). Mounts `/static` + `/media`, Prometheus at `/metrics`, Jinja UI from `templates/` via `routers/ui_route.py`.
- **Worker**: `worker.py` — `brpop`s JSON `QueueMessage`s from the Redis list (`redis_queue_name`) and drives the huuto.net API (`huutobot.py`) to add/relist/close items. Runs its own Prometheus server on `settings.worker_prometheus_port`.

Readiness: `GET /health` (liveness) and `GET /health/ready` (pings DB + Redis, 503 on failure).

No automated tests. Root scripts are ad-hoc: `test_client.py` pushes random queue messages, `populate_*.py` seed DB data, `sqlalchemy_test.py` is a scratch query file. Verify changes with mypy + manual requests.

## Commands
- Package manager is **uv**, Python 3.14 (`.python-version`; `pyproject` floor is `>=3.13`).
- `uv sync` installs deps + the single dev tool (mypy). `uv sync --frozen` for dep changes (this is what the Dockerfiles use).
- `uv run mypy .` is the only static check — there is no ruff/pytest/lint config. It passes clean on 39 files; keep it that way. `# type: ignore` is used liberally and is expected.

## Traps
- `requirements.txt` is **generated — never hand-edit it.** Regenerate after any dependency change with `uv export --no-hashes --no-dev --no-emit-project --output-file requirements.txt`. `pyproject.toml` + `uv.lock` are the source of truth. Only `Dockerfile.huutoapi.pip` consumes it.
- **`Dockerfile.huutoapi.pip` is broken** — it runs `uvicorn app.main:app`, but there is no `app/` package (the module is `main:app`). Don't use it as a reference. Real images are `Dockerfile.huutoapi` / `Dockerfile.huutoworker` (multi-stage uv + alpine, non-root `appuser`).
- `AGENTS.md` is listed in `.gitignore`, so it is intentionally untracked. `git status` showing ` D AGENTS.md` is expected — don't "restore" or commit it.
- `models/__init__.py` (and `schemas/`, `routers/`, `common/`) are **empty** — no auto-imports. A model is only registered with `Base.metadata` if something imported it first.

## Config & secrets
- `config.py` (pydantic-settings) reads `.env`/env and instantiates `settings` at **import time**. Every field is required, so one missing var breaks every import of `config` with a hard failure.
- No `.env`/`.env.example` is committed — create one locally.
- Gotcha: `db.py` does **not** use the `database_user`/`database_password` settings. Both engines use a custom `creator`/`async_creator` that read `username` and `password` files from `settings.database_credential_dir` on every new connection (rotating short-lived creds). Those files must exist or nothing connects.
- In-cluster, `./update_creds.sh` populates them from the k8s secret `huutoapp-dynamic-creds` (ns `huutoapp`) — it is the only source of those creds in production, so the dir must be writable in the container.
- `LoggingConfigListener` opens `settings.logging_config_port` and serves `logging.config.listen`, allowing runtime log-level reconfiguration from outside.
- `redis_password` in `docker.compose` is `teevee888`.

## Local infra
- `docker compose -f docker.compose up` (note: no `.yml` extension) starts Postgres (`database`, user/db/password all `huutoapp`, 5432) and Redis (`cache`, 6379).
- `main.py` mounts `static/` and `media/` at startup, so both must exist (`media/icons` and `static/.gitkeep` are tracked; `media/images/` is gitignored and created on demand by `image_utils.py`).

## DB & schema
- There is no Alembic and no migrations — Alembic was removed from deps. Schema is managed out-of-band; `models/` is the reference.
- `python sync-db.py` runs `Base.metadata.create_all`, but it only imports `models.user_model`, so **it creates the `users` table only**. Import the other models in that script if you need the full schema.
- API uses the async engine (`AsyncSessionLocal` / `get_db`); the worker uses the sync engine (`sync_engine`). Both are created in `db.py` with `pool_recycle=300`, `pool_pre_ping=True`.
- `python populate_config.py` (`item_config.json` + `movie_categories.json`) and `python populate_test_data.py` both **clear tables and restart sequences** — destructive.

## Auth
- `auth.py`: argon2 hashing via `pwdlib`, JWT access tokens via `pyjwt` (`secret_key`/`algorithm`/`access_token_expire_minutes` in `.env`). Deps: `CurrentUser = Annotated[User, Depends(get_current_user)]` and `require_admin = require_roles(UserRole.admin)`.
- `routers/users_route.py` login (`POST /api/v1/users/token`) treats the OAuth2 `username` form field as **email**.
- Auth is currently wired **only** into `users_route.py`. `items_route.py`, `ui_route.py`, and the other routers are still unauthenticated — don't assume a dependency is present.
- `models/user_model.py` stores a `role` `Enum(common_types.UserRole)` (`user`/`admin`). Adding a role means editing `common/common_types.py` **and** a DB enum migration, which does not exist here.

## Queue flow (worker)
- Messages are `schemas/huutoapp_queue_schema.QueueMessage` JSON. The API `lpush`es (via `worker_utils.create_queue_msg`, which first writes a `task_log` row using the **sync** engine); the worker `brpop`s and `match`es on `common/common_types.TaskType` in `worker.py:process_message`.
- `UpdateItem`, `AddImage`, and `DeleteImage` task types are declared but **not implemented** — they log an error and return `None`.
- Progress is recorded in the `task_log` table via `worker_utils.update_status` (JSON `details` + `flag_modified`).
- On `HuutoItemError` the worker deletes the failed huuto.net draft and re-pushes up to `settings.max_retries`.
- `brpop`/`socket_timeout` values in `redis_queue.py` and `worker.py` were raised for redis 7.4.0 → 8.0.1; don't lower them without testing in K8s.

## CI/CD
- `.github/workflows/build_and_sign.yaml`: builds `huutoapi`/`huutoworker`, cosign-signs, pushes to Docker Hub — triggered **only** by `v*` tags.
- `Jenkinsfile`: separate pipeline (kaniko + cosign) pushing to `harbor.anyman.homelab` as `huutoapp/huutoapi` and `huutoapp/huutoworker`, tagged `dev-${BUILD_NUMBER}` or the release tag.

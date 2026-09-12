# AGENTS.md

## Project
HuutoApp: huuto.net listing automation. Two processes share Postgres + a Redis list queue:
- **API**: FastAPI app in `main.py` (run: `uvicorn main:app --port 8000`). Mounts `/static` and `/media`; Prometheus at `/metrics`.
- **Worker**: `worker.py` — `brpop`s JSON `QueueMessage`s from the Redis list (`redis_queue_name`) and drives the huuto.net API (`huutobot.py`) to add/relist/close items. Exposes its own Prometheus server on `settings.worker_prometheus_port`.

No automated tests. Root scripts are ad-hoc: `test_client.py` pushes random queue messages, `populate_*.py` seed DB data, `sqlalchemy_test.py` is a scratch query file.

## Tooling
- Package manager is **uv** (Python 3.14). `uv sync` to install; use `uv sync --frozen` for dep changes. Only dev tool is mypy (`uv run mypy .`). No ruff/pytest/lint config; rely on mypy + manual verification. `# type: ignore` comments are used liberally and expected.

## Config & secrets
- `config.py` (pydantic-settings) reads from `.env`/env — every setting is required and any missing one makes every import of `config` fail. No `.env` or `.env.example` is committed; create one locally.
- Gotcha: `db.py` does NOT use `database_user`/`database_password` settings. It reads `username` and `password` files from `settings.database_credential_dir` (short-lived creds). Local dev must create those files.
- `redis_password` in `docker.compose` is `teevee888`.

## Local infra
- `docker compose -f docker.compose up` (note: file has no `.yml` extension) starts Postgres (`database`, user/db `huutoapp`) and Redis (`cache`, port 6379).
- The app fails to start if `media/` doesn't exist (mounted statically; images go in `media/images/`).

## DB & schema
- Alembic is a dependency but there's no alembic config/migrations and nothing calls `create_all` — the schema is managed out-of-band; `models/` is the reference.
- Seed lookup tables with `python populate_config.py` (`item_config.json` + `movie_categories.json`), sample items with `python populate_test_data.py`. Both clear tables AND restart sequences — destructive.
- API uses the async engine (`AsyncSessionLocal`); the worker uses the sync engine (`sync_engine`), both from `db.py`.

## Queue flow (worker)
- Queue messages are `huutoapp_queue_schema.QueueMessage` JSON. The API `lpush`es; the worker `brpop`s and dispatches on `common/common_types.TaskType` in `worker.py:process_message`.
- Task progress is recorded in the `task_log` table via `worker_utils.update_status` (JSON `details` + `flag_modified`).
- On `HuutoItemError` the worker deletes the failed huuto.net draft and re-pushes the message up to `settings.max_retries`.

## CI/CD
- `.github/workflows/build_and_sign.yaml`: builds `huutoapi`/`huutoworker` images (Dockerfile.huutoapi / Dockerfile.huutoworker), cosign-signs, pushes to Docker Hub — triggered only by `v*` tags.
- `Jenkinsfile`: separate pipeline pushing to `harbor.anyman.homelab` (`dev-${BUILD_NUMBER}` or release tag).
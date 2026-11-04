# checkout

A small FastAPI + SQLAlchemy + MySQL playground, served behind Apache.

## Stack

- **uv** — dependencies, virtualenv, running commands
- **FastAPI** + **Uvicorn** — web framework / ASGI server
- **SQLAlchemy 2** + **Alembic** — ORM and schema migrations
- **PyMySQL** — MySQL driver
- **pydantic-settings** — config from env / `.env`
- **pytest**, **ruff**, **mypy** — tests, lint/format, type checks

## Layout

```
src/checkout/
  main.py          FastAPI app + /health
  config.py        settings (DATABASE_URL, DEBUG)
  db.py            engine, Base, per-request session dependency
  models.py        ORM tables
  schemas.py       Pydantic request/response models
  routers/items.py CRUD example
migrations/        Alembic migrations
tests/             pytest (uses in-memory SQLite, no MySQL needed)
deploy/            systemd unit + Apache vhost
```

## Setup

```bash
# 1. MySQL database + user
sudo mysql -e "CREATE DATABASE app CHARACTER SET utf8mb4; \
  CREATE USER 'app'@'localhost' IDENTIFIED BY 'changeme'; \
  GRANT ALL ON app.* TO 'app'@'localhost';"

# 2. Config
cp .env.example .env   # adjust credentials

# 3. Install deps and create tables
uv sync
uv run alembic upgrade head
```

## Develop

```bash
uv run fastapi dev src/checkout/main.py   # http://127.0.0.1:8000, docs at /docs
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy
```

Schema changes: edit `models.py`, then
`uv run alembic revision --autogenerate -m "describe change"` and `uv run alembic upgrade head`.

## Deploy behind Apache

```
https://HOST/api/...  ->  Apache :443 (TLS, mkcert cert)  ->  uvicorn 127.0.0.1:8100 (systemd "checkout")  ->  MySQL
```

- `deploy/deploy.sh` copies the code to `/srv/checkout`, installs locked deps into its own venv,
  runs `alembic upgrade head`, installs `deploy/checkout.service` and restarts it.
  On first run it copies `.env` to `/srv/checkout/.env` (root:www-data, 0640); later edits go there.
- `deploy/apache-checkout.conf` is the proxy snippet inside the `*:443` vhost
  (`/etc/apache2/sites-available/default-ssl.conf`). Apache strips `/api`; uvicorn's `--root-path /api`
  makes docs/redirects use the public prefix.
- Dev server (`fastapi dev`, port 8000) and the service (port 8100) can run side by side.

```bash
deploy/deploy.sh                       # redeploy after code changes
systemctl status checkout              # service state
journalctl -u checkout -f              # app logs
```

API: https://localhost/api/items, docs at https://localhost/api/docs

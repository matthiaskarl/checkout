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

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the web app (`checkout`)
plus independent library packages in `packages/`.

```
src/checkout/              FastAPI app (backend)
  main.py                  app, /api + /ui prefixes, /api/health
  config.py                settings (DATABASE_URL, DEBUG)
  db.py                    engine, Base, per-request session dependency
  models.py                ORM tables
  schemas.py               Pydantic request/response models
  routers/items.py         /api/items: CRUD example
  routers/dice.py          /api/dicesim: JSON adapter around the dicesim library
  routers/pages.py         /ui/...: server-rendered Jinja2 pages
  templates/               Jinja2 templates (base.html + pages)
frontend/                  React app (Vite + React + TypeScript), served by Apache at /app/
  index.html               HTML shell with <div id="root">; Vite injects the built JS/CSS
  src/main.tsx             entry point: mounts <App /> into #root
  src/App.tsx              the page component (state, form, items table)
  src/App.css              styles
  src/api.ts               typed fetch client for /api (mirrors schemas.py)
  vite.config.ts           base /app/, dev proxy /api -> uvicorn :8000
  package.json             npm scripts (dev, build, lint) + dependencies; package-lock.json pins versions
  dist/                    build output (npm run build), not in git
migrations/                Alembic migrations
tests/                     pytest (uses in-memory SQLite, no MySQL needed)
deploy/                    systemd unit, Apache snippet, deploy.sh
packages/dicesim/          standalone library + CLI (no dependencies), see below
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
uv run fastapi dev src/checkout/main.py   # http://127.0.0.1:8000, docs at /api/docs
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy
```

Schema changes: edit `models.py`, then
`uv run alembic revision --autogenerate -m "describe change"` and `uv run alembic upgrade head`.

## dicesim (library + CLI)

Probability of reaching a symbol goal with 5 keep-and-reroll dice in 3 rolls
(faces 1,2,3 → A; 4,5 → B; 6 → C), either simulated (Monte Carlo, `simulation.py`) or
calculated exactly (recursion over "symbols still missing × rolls left", `exact.py`).
Standard library only; no FastAPI, no database.

```bash
uv run dicesim A A A B C                 # P(A A A B C within 3 rolls) ≈ 0.56  (± 0.01, ...)
uv run dicesim A A A B C --exact         # P(A A A B C within 3 rolls) = 0.5597  (exact)
uv run dicesim A A A B C --trials 300    # fewer trials -> wider margin (± ~0.06)
uv run dicesim B C --json --seed 42      # machine-readable, reproducible
uv run dicesim --help                    # --rolls, --dice, --faces A,A,A,B,B,C
```

```python
from dicesim import exact_probability, simulate

exact_probability(["A", "A", "A", "B", "C"])  # 0.5597...
result = simulate(["A", "A", "A", "B", "C"], trials=10_000, seed=42)  # estimate
result.probability, result.standard_error
```

Build it on its own: `uv build --package dicesim` (wheel works with any Python ≥ 3.11).

Over HTTP (`src/checkout/routers/dice.py`, a thin adapter around the library):

```bash
curl 'https://localhost/api/dicesim?goal=AAABC'                                        # exact (default)
curl 'https://localhost/api/dicesim?goal=AAABC&method=simulation&trials=20000&seed=1'  # trials ≤ 100000
```
Invalid goals return 422 in FastAPI's usual `{"detail": [{"loc": ["query", "goal"], "msg": ...}]}` format.

## Frontends (two examples of the same "create item" page)

| | URL | Code | Rendering |
|---|---|---|---|
| Jinja2 | https://localhost/ui/items/new | `src/checkout/routers/pages.py`, `src/checkout/templates/` | server: Python builds the HTML, form posts, page reloads |
| React | https://localhost/app/ | `frontend/` (Vite + React + TypeScript) | browser: JS builds the DOM, talks JSON to `/api/items` |

React development (hot reload; `/api` is proxied to the uvicorn dev server on :8000):

```bash
uv run fastapi dev src/checkout/main.py   # terminal 1: backend
cd frontend && npm install && npm run dev  # terminal 2: http://localhost:5173/app/
npm run lint && npm run build              # lint (oxlint), type-check + production build to frontend/dist/
```

## Deploy behind Apache

```
https://HOST/api/...  ->  Apache :443 (TLS, mkcert cert)  ->  uvicorn 127.0.0.1:8100 (systemd "checkout")  ->  MySQL
https://HOST/ui/...   ->  Apache :443  ->  uvicorn (same app, Jinja2 pages)
https://HOST/app/...  ->  Apache :443  ->  static files in /srv/checkout/frontend (React build)
```

- `deploy/deploy.sh` copies the code to `/srv/checkout`, installs locked deps into its own venv,
  runs `alembic upgrade head`, builds the React frontend and copies it to `/srv/checkout/frontend`,
  installs `deploy/checkout.service` and restarts it.
  On first run it copies `.env` to `/srv/checkout/.env` (root:www-data, 0640); later edits go there.
- `deploy/apache-checkout.conf` is the proxy + static-files snippet inside the `*:443` vhost
  (`/etc/apache2/sites-available/default-ssl.conf`). Paths are forwarded unchanged: the app itself
  defines the `/api` (JSON) and `/ui` (HTML) prefixes, so dev and production URLs are identical.
- Dev server (`fastapi dev`, port 8000) and the service (port 8100) can run side by side.

```bash
deploy/deploy.sh                       # redeploy after code changes
systemctl status checkout              # service state
journalctl -u checkout -f              # app logs
```

API: https://localhost/api/items, https://localhost/api/dicesim, docs at https://localhost/api/docs, Jinja2 page: https://localhost/ui/items/new

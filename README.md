# checkout

A learning playground for current Python web development: a small **admin UI for one database
table** (`items`), built twice, with server-rendered **Jinja2 + htmx** and with a **React** SPA.
Both share one FastAPI backend with login, CSRF protection and a public API protected by API keys.
It runs behind Apache with MySQL.

(The name is historical. Shop and business logic may come later as a separate branch-out.)

## Contents

- [Stack](#stack)
- [What's where (URLs)](#whats-where-urls)
- [Layout](#layout)
- [Setup](#setup)
- [Develop](#develop)
- [Authentication and security](#authentication-and-security)
- [The two frontends](#the-two-frontends)
- [dicesim (library, CLI, API)](#dicesim-library-cli-api)
- [Deploy behind Apache](#deploy-behind-apache)
- [Ideas for later](#ideas-for-later)

## Stack

| Area | Tools |
|---|---|
| Python tooling | **uv** (dependencies, venv, workspace), **ruff** (lint/format), **mypy** (strict), **pytest** |
| Backend | **FastAPI** + **Uvicorn**, **Pydantic** / pydantic-settings |
| Database | **MySQL 8**, **SQLAlchemy 2** (typed ORM), **Alembic** (migrations), PyMySQL |
| Server-rendered UI | **Jinja2** templates, **htmx 2** (vendored in `src/checkout/static/`) |
| SPA | **React 19** + **TypeScript**, **React Router 8**, **Vite** (dev server + build), oxlint |
| Auth | **pwdlib** (argon2id password hashes), server-side sessions, CSRF tokens, API keys |
| Hosting | **Apache 2** (TLS via mkcert, reverse proxy, static files), **systemd** |

## What's where (URLs)

Same paths in development and production. Only the host differs: dev is `http://localhost:8000`
for the backend and `http://localhost:5173` for React, production is `https://localhost`.

| Path | What | Auth |
|---|---|---|
| `/ui/` | Jinja2 + htmx admin UI (redirects to `/ui/items`) | session cookie (login form) |
| `/ui/login` | login page for both frontends | public |
| `/app/` | React admin UI (same features) | session cookie (own login form) |
| `/api/items` | JSON CRUD for items | session cookie + CSRF header for writes |
| `/api/session` | JSON login/logout/"who am I" for React | public / session |
| `/api/dicesim` | public JSON API (dice probability) | API key (`Authorization: Bearer`) **or** session |
| `/api/health` | app + database check | public |
| `/api/docs` | OpenAPI / Swagger UI ("Authorize" for API key and CSRF token) | public |

## Layout

This is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/): the web app
(`checkout`) plus independent library packages in `packages/`.

```
src/checkout/                 FastAPI app (backend)
  main.py                     app, router wiring, /api/health, static files, login redirect
  config.py                   settings from env / .env (DATABASE_URL required)
  db.py                       engine, Base, per-request DB session dependency
  models.py                   ORM tables: User, LoginSession, ApiKey, Item
  schemas.py                  Pydantic request/response models
  security.py                 password hashing (argon2id)
  users.py                    user accounts (no HTTP)
  sessions.py                 login + server-side sessions (no HTTP)
  apikeys.py                  API keys (no HTTP)
  auth.py                     HTTP side: cookie, dependencies (require_user, require_csrf, ...)
  cli.py                      `checkout-admin` command (users, API keys)
  templating.py               shared Jinja2 environment (+ csrf_token in every template)
  routers/
    items.py                  /api/items: JSON CRUD
    session_api.py            /api/session: JSON login for the SPA
    dice.py                   /api/dicesim: JSON adapter around the dicesim library
    login.py                  /ui/login, /ui/logout
    pages.py                  /ui/items...: list, new/edit form, delete, inline-edit row fragments
    dice_ui.py                /ui/dice: htmx fragment for the dice section
  templates/                  base.html, pages, and _partials (fragments htmx swaps in)
  static/                     htmx, confirm-dialog.js
frontend/                     React SPA (Vite + TypeScript), served by Apache at /app/
  index.html                  HTML shell with <div id="root">; Vite injects the built JS/CSS
  src/main.tsx                entry: <BrowserRouter basename="/app"> + <App />
  src/App.tsx                 login gate, layout, routes
  src/api.ts                  typed fetch client: CSRF header, 401 handling, all API calls
  src/LoginForm.tsx           login
  src/ItemsListPage.tsx       list, notices, delete
  src/ItemFormPage.tsx        new + edit (one component)
  src/ItemRow.tsx             table row with inline editing
  src/ConfirmDialog.tsx       <dialog> for delete
  src/DiceSection.tsx         dice probability section
  vite.config.ts              base /app/, dev proxy /api -> uvicorn :8000
migrations/                   Alembic migrations
tests/                        pytest (in-memory SQLite, no MySQL needed)
deploy/                       systemd unit, Apache snippet, deploy.sh
packages/dicesim/             standalone library + CLI (no dependencies), see below
```

Pattern used throughout: **logic without HTTP** (`users.py`, `sessions.py`, `apikeys.py`, `dicesim`)
plus **thin adapters** (JSON routers, HTML routers, CLI) that call it.

## Setup

```bash
# 1. MySQL database + user
sudo mysql -e "CREATE DATABASE app CHARACTER SET utf8mb4; \
  CREATE USER 'app'@'localhost' IDENTIFIED BY 'changeme'; \
  GRANT ALL ON app.* TO 'app'@'localhost';"

# 2. Config
cp .env.example .env              # adjust credentials

# 3. Dependencies, tables, first user
uv sync
uv run alembic upgrade head
uv run checkout-admin create-user alice     # asks for the password (min. 12 characters)

# 4. Frontend dependencies
cd frontend && npm install
```

## Develop

```bash
uv run fastapi dev src/checkout/main.py     # terminal 1: backend, http://localhost:8000/ui/
cd frontend && npm run dev                  # terminal 2: React, http://localhost:5173/app/
```
Log in once on either frontend: they share the session cookie (cookies ignore the port, and the
Vite dev server proxies `/api` to the backend).

```bash
uv run pytest                               # backend tests (+ doctests)
uv run ruff check . && uv run ruff format .
uv run mypy
cd frontend && npm run lint && npm run build   # oxlint, type check + production build
```

**Schema changes:** edit `models.py`, then
`uv run alembic revision --autogenerate -m "describe change"`, **read the generated file**
(autogenerate sees the schema, not the data; see `e8222a338978` for a hand-edited example), then
`uv run alembic upgrade head`. New migrations are linted and formatted by ruff automatically
(post-write hooks in `alembic.ini`).

## Authentication and security

**Users.** Passwords are stored as argon2id hashes (`security.py`), never in plain text. Users are
created on the command line:

```bash
uv run checkout-admin create-user NAME        # password via hidden prompt (or --password-stdin)
uv run checkout-admin list-users [--show-hashes]
```

**Sessions (both frontends).** A login creates a row in `login_sessions`. The browser gets an
`HttpOnly; Secure; SameSite=Lax` cookie with a random token, and the database stores only its
SHA-256. Logout or deleting the row ends the session immediately. Sessions last 7 days.
Deactivating a user (`is_active`) ends all of their sessions.

- HTML pages: anonymous visitors are redirected to `/ui/login?next=...` (`next` is checked against
  open redirects).
- JSON API: anonymous requests get `401`.

**CSRF.** Two layers for every state-changing request (POST/PATCH/PUT/DELETE):
1. App-wide: requests that the browser marks as foreign (`Sec-Fetch-Site: same-site` / `cross-site`)
   are rejected with `403`.
2. Per session: a `csrf_token` that has to be sent back. Plain forms send it as a hidden field,
   htmx as a header (`hx-headers` on `<body>`), and React as an `X-CSRF-Token` header, with the
   token taken from `GET /api/session`.

**API keys (`/api/dicesim`).** For scripts and other programs. Keys start with `ck_`, are shown
once, and are stored only as SHA-256. Without a key, a logged-in browser session works too.

```bash
uv run checkout-admin create-api-key NAME --name "what it's for"
uv run checkout-admin list-api-keys            # prefix, owner, last use (never the key)
uv run checkout-admin revoke-api-key ID

curl -H "Authorization: Bearer ck_..." 'https://localhost/api/dicesim?goal=AAABC'
```

## The two frontends

Both offer the same features: item list, create, edit page, delete with a custom `<dialog>`,
inline editing in the table, and a collapsible dice-probability section.

| | Jinja2 + htmx (`/ui/`) | React (`/app/`) |
|---|---|---|
| Who builds the HTML | server (Python, Jinja2 templates) | browser (React components) |
| Data from the server | HTML, full pages or fragments | JSON from `/api/...` |
| Partial updates | htmx swaps fragments (`hx-get`, `hx-put`, `hx-target`) | React state changes re-render components |
| Without JavaScript | still works (forms post normally, links open pages) | blank page |
| Code | `routers/pages.py`, `templates/` | `frontend/src/` |

The pieces map almost 1:1 between the two versions:

| Jinja2 + htmx | React |
|---|---|
| `items_list.html` | `ItemsListPage.tsx` |
| `item_form.html` | `ItemFormPage.tsx` |
| `_item_row.html`, `_item_row_edit.html` | `ItemRow.tsx` |
| `<dialog>` + `confirm-dialog.js` | `ConfirmDialog.tsx` |
| `_dice.html`, `_dice_result.html` | `DiceSection.tsx` |

## dicesim (library, CLI, API)

Probability of reaching a symbol goal with 5 keep-and-reroll dice in 3 rolls
(faces 1,2,3 → A; 4,5 → B; 6 → C). It can be simulated (Monte Carlo, `simulation.py`) or
calculated exactly (recursion over "symbols still missing × rolls left", `exact.py`).
Standard library only: no FastAPI, no database.

```bash
uv run dicesim A A A B C                 # P(A A A B C within 3 rolls) ≈ 0.56  (± 0.01, ...)
uv run dicesim A A A B C --exact         # = 0.5597
uv run dicesim B C --json --seed 42      # machine-readable, reproducible
uv run dicesim --help                    # --trials, --rolls, --dice, --faces A,A,A,B,B,C
```

```python
from dicesim import exact_probability, simulate

exact_probability(["A", "A", "A", "B", "C"])                          # 0.5597...
result = simulate(["A", "A", "A", "B", "C"], trials=10_000, seed=42)  # estimate
result.probability, result.standard_error
```

It's used three ways:
- `uv run dicesim` on the command line
- `/ui/dice` (Jinja2), which calls the library directly and returns an HTML fragment
- `/api/dicesim` (JSON), which React and API-key clients use:
  ```
  GET /api/dicesim?goal=AAABC                                       # exact (default)
  GET /api/dicesim?goal=AAABC&method=simulation&trials=20000&seed=1 # trials ≤ 100000
  ```
  Invalid goals return `422` in FastAPI's `{"detail": [{"loc": [...], "msg": ...}]}` format.

Build it on its own: `uv build --package dicesim` (the wheel works with any Python ≥ 3.11).

## Deploy behind Apache

```
https://HOST/api/... ┐
https://HOST/ui/...  ┴─> Apache :443 (TLS) ─> uvicorn 127.0.0.1:8100 (systemd "checkout") ─> MySQL
https://HOST/app/... ──> Apache :443 ─> static files in /srv/checkout/frontend (React build)
```

```bash
deploy/deploy.sh                       # (re)deploy
systemctl status checkout              # service state
journalctl -u checkout -f              # app logs
```

- `deploy/deploy.sh`:
  - copies the code to `/srv/checkout` and installs the locked dependencies into its own venv
  - runs `alembic upgrade head`
  - builds the React app and copies it to `/srv/checkout/frontend`
  - installs and restarts `deploy/checkout.service`

  On the first run it copies `.env` to `/srv/checkout/.env` (root:www-data, 0640); later edits go
  there. For the admin CLI against the deployed database (it reads `.env` from the current
  directory): `cd /srv/checkout && sudo -u www-data .venv/bin/checkout-admin ...`
- `deploy/apache-checkout.conf` is the snippet inside the `*:443` vhost
  (`/etc/apache2/sites-available/default-ssl.conf`):
  - `/api/` and `/ui/` are proxied to uvicorn with their paths unchanged, since the app defines
    those prefixes itself
  - `/app/` is served as static files, with a fallback to `index.html` for deep links like
    `/app/items/5/edit`
  - cache headers: `index.html` is never cached, the hashed `assets/` are cached forever
- The dev server (port 8000) and the service (port 8100) can run side by side.

## Ideas for later

- Security: JWT / OpenID Connect, CORS for `/api/dicesim`, rate limiting / login throttling
- Data: bulk create and "edit all" (one form, many rows), optimistic locking against lost updates
- UI: sorting, search and pagination for the table; notices and highlights that fade out;
  flash messages instead of `?created=` in the URL

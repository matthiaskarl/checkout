#!/usr/bin/env bash
# Deploy this checkout to /srv/checkout: backend (venv + migrations + systemd service)
# and the React frontend build (static files served by Apache at /app/).
# Usage: deploy/deploy.sh        (needs sudo; uv must be on PATH or set UV=/path/to/uv)
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST=/srv/checkout
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

echo "==> Copying code to $DEST"
sudo install -d -m 755 -o root -g root "$DEST"
for f in pyproject.toml uv.lock .python-version alembic.ini; do
    sudo install -m 644 -o root -g root "$SRC/$f" "$DEST/$f"
done
for d in src migrations; do
    sudo rsync -a --delete --chown=root:root --exclude='__pycache__' "$SRC/$d/" "$DEST/$d/"
done

if [ ! -f "$DEST/.env" ]; then
    echo "==> No $DEST/.env yet, copying $SRC/.env"
    sudo install -m 640 -o root -g www-data "$SRC/.env" "$DEST/.env"
fi

echo "==> Installing dependencies (locked, no dev deps)"
sudo env UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy \
    "$UV" sync --project "$DEST" --frozen --no-dev --no-editable --compile-bytecode -q

echo "==> Running migrations"
sudo sh -c "cd '$DEST' && .venv/bin/alembic upgrade head"

echo "==> Building frontend (React) and copying to $DEST/frontend"
(
    cd "$SRC/frontend"
    [ -d node_modules ] || npm ci --no-audit --no-fund
    npm run build --silent
)
sudo rsync -a --delete --chown=root:root --chmod=D755,F644 "$SRC/frontend/dist/" "$DEST/frontend/"

echo "==> Installing and restarting service"
sudo install -m 644 -o root -g root "$SRC/deploy/checkout.service" /etc/systemd/system/checkout.service
sudo systemctl daemon-reload
sudo systemctl enable -q checkout
sudo systemctl restart checkout
sleep 2
systemctl is-active checkout

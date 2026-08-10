#!/bin/sh
# Create persistent Docker settings on first boot, then run the command.

set -eu

DATA_DIR="${NEWS_DATA_DIR:-/data}"
CONFIG_PATH="${NEWS_CONFIG:-$DATA_DIR/config.toml}"
DEFAULT_CONFIG_PATH="/app/config.toml"

# The container serves as an unprivileged account, so it cannot take ownership
# of the mounted directory itself. Failing here with the exact command to run
# is clearer than a permission error from the first write.
mkdir -p "$DATA_DIR" 2>/dev/null || true
if [ ! -w "$DATA_DIR" ]; then
    echo "[startup] ERROR: $DATA_DIR is not writable by this container."
    echo "[startup] The container runs as user id $(id -u), group id $(id -g)."
    echo "[startup] On the host, run:"
    echo "[startup]   mkdir -p \${HOME}/.containers/news"
    echo "[startup]   sudo chown -R \$(id -u):\$(id -g) \${HOME}/.containers/news"
    echo "[startup] then set NEWS_UID and NEWS_GID in .env to your own"
    echo "[startup] 'id -u' and 'id -g' values and start the container again."
    exit 1
fi

# Keep operator changes in the mounted data directory across image upgrades.
if [ ! -f "$CONFIG_PATH" ]; then
    cp "$DEFAULT_CONFIG_PATH" "$CONFIG_PATH"
    echo "[startup] Created $CONFIG_PATH from the image defaults"
fi

# Make a missing sign-in account obvious here, because the server answers
# every request with 401 until the first account is complete. The optional
# UI_USERNAME_2 and UI_USERNAME_3 accounts are checked by the server itself.
if [ -z "${UI_USERNAME:-}" ] || [ -z "${UI_PASSWORD:-}" ]; then
    echo "[startup] WARNING: UI_USERNAME or UI_PASSWORD is unset; the server"
    echo "[startup] will refuse every request. Set both in .env beside"
    echo "[startup] docker-compose.yml and restart."
fi

exec "$@"

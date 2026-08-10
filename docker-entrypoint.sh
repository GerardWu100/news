#!/bin/sh
# Create persistent Docker settings on first boot, then run the command.

set -eu

DATA_DIR="${NEWS_DATA_DIR:-/data}"
CONFIG_PATH="${NEWS_CONFIG:-$DATA_DIR/config.toml}"
DEFAULT_CONFIG_PATH="/app/config.toml"

# Keep operator changes in the mounted data directory across image upgrades.
mkdir -p "$DATA_DIR"
if [ ! -f "$CONFIG_PATH" ]; then
    cp "$DEFAULT_CONFIG_PATH" "$CONFIG_PATH"
    echo "[startup] Created $CONFIG_PATH from the image defaults"
fi

# Make a missing sign-in account obvious here, because the server answers
# every request with 401 until both values are present.
if [ -z "${UI_USERNAME:-}" ] || [ -z "${UI_PASSWORD:-}" ]; then
    echo "[startup] WARNING: UI_USERNAME or UI_PASSWORD is unset; the server"
    echo "[startup] will refuse every request. Set both in .env beside"
    echo "[startup] docker-compose.yml and restart."
fi

exec "$@"

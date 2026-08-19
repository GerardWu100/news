#!/bin/sh
# Create persistent Docker settings on first boot, then run the command.

set -eu

DATA_DIR="${NEWS_DATA_DIR:-/data}"
CONFIG_PATH="${NEWS_CONFIG:-$DATA_DIR/config.toml}"
DEFAULT_CONFIG_PATH="/app/config.toml"

# Seed the mounted data directory on first boot. A custom NEWS_CONFIG may point
# at a nested location inside that mount, so create its parent as well.
mkdir -p "$DATA_DIR"
mkdir -p "$(dirname "$CONFIG_PATH")"

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

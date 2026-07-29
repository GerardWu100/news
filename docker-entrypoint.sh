#!/bin/sh
# Seed persistent Docker configuration, then run the requested command.

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

exec "$@"

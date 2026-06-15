#!/bin/sh
set -e
if [ -n "$CONFIG_URL" ]; then
    mkdir -p /config
    curl -fsSL "$CONFIG_URL" -o /config/config.yaml
fi
exec tver-dl "$@"

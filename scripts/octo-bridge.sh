#!/usr/bin/env bash
# Octo local API bridge: exposes 0.0.0.0:58889 -> 127.0.0.1:58888
# Run this on the same host where Octo Browser is running (Linux/macOS).
# Then set OCTO_LOCAL_API_URL=http://host.docker.internal:58889 in .env (or your host IP).

set -e

OCTO_PORT="${OCTO_PORT:-58888}"
BRIDGE_PORT="${BRIDGE_PORT:-58889}"

if ! command -v socat &>/dev/null; then
  echo "socat is required. Install it:"
  echo "  Debian/Ubuntu: sudo apt install socat"
  echo "  macOS:         brew install socat"
  exit 1
fi

echo "Octo bridge: 0.0.0.0:${BRIDGE_PORT} -> 127.0.0.1:${OCTO_PORT}"
echo "Press Ctrl+C to stop."
exec socat TCP-LISTEN:"${BRIDGE_PORT}",fork,reuseaddr TCP:127.0.0.1:"${OCTO_PORT}"

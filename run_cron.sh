#!/usr/bin/env bash
# Cron entrypoint: check whether a closed period needs an invoice email.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${ROOT}/logs"
mkdir -p "${LOG_DIR}"

export DISPLAY="${DISPLAY:-:0}"
if [[ -z "${XDG_RUNTIME_DIR:-}" && -d "/run/user/$(id -u)" ]]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi
if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -S "${XDG_RUNTIME_DIR:-/dev/null}/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=${XDG_RUNTIME_DIR}/bus"
fi

cd "${ROOT}"
exec "${ROOT}/.venv/bin/python" "${ROOT}/generate_invoice.py" --if-needed

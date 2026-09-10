#!/usr/bin/env bash
# Install/update the project crontab entry for invoice checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${ROOT}/.venv/bin/activate" 2>/dev/null || true

HOUR="$(
  "${ROOT}/.venv/bin/python" -c "import _config_params as c; print(getattr(c, 'CRON_HOUR', 9))"
)"
MINUTE="$(
  "${ROOT}/.venv/bin/python" -c "import _config_params as c; print(getattr(c, 'CRON_MINUTE', 0))"
)"

MARKER_BEGIN="# BEGIN payments-mouri"
MARKER_END="# END payments-mouri"
CRON_LINE="${MINUTE} ${HOUR} * * * ${ROOT}/run_cron.sh >> ${ROOT}/logs/cron.log 2>&1"
BLOCK="${MARKER_BEGIN}
${CRON_LINE}
${MARKER_END}"

chmod +x "${ROOT}/run_cron.sh" "${ROOT}/install_cron.sh"

EXISTING="$(crontab -l 2>/dev/null || true)"
FILTERED="$(printf '%s\n' "${EXISTING}" | awk -v b="${MARKER_BEGIN}" -v e="${MARKER_END}" '
  $0 == b {skip=1; next}
  $0 == e {skip=0; next}
  !skip {print}
')"

{
  printf '%s\n' "${FILTERED}" | sed -e '${/^$/d;}'
  printf '%s\n' "${BLOCK}"
} | crontab -

echo "Installed cron job:"
echo "  ${CRON_LINE}"
crontab -l | sed -n "/${MARKER_BEGIN}/,/${MARKER_END}/p"

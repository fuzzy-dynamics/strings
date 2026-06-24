#!/usr/bin/env bash
# setup_kernels.sh — best-effort install of external decision-procedure kernels
# into an isolated venv, so Witsoc certificate re-checking can independently
# re-decide SAT/SMT certificates. Never touches system packages.
#
# Installs (pip): z3-solver, cvc5.  Detects (system, not installed here):
# drat-trim, cadical/kissat, PARI/gp — reported in toolchain_status.json.
#
# Usage: setup_kernels.sh [venv_dir]   (default: ~/.witsoc/kernels-venv)
set -uo pipefail

VENV="${1:-$HOME/.witsoc/kernels-venv}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STATUS="$SCRIPT_DIR/toolchain_status.json"

echo "witsoc: setting up kernel venv at $VENV" >&2
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV" || { echo "venv creation failed" >&2; exit 1; }
fi

"$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
for pkg in z3-solver cvc5; do
  echo "witsoc: pip install $pkg ..." >&2
  "$VENV/bin/pip" install --quiet "$pkg" >/dev/null 2>&1 \
    && echo "  ok: $pkg" >&2 || echo "  skip: $pkg (offline or unavailable)" >&2
done

export WITSOC_KERNEL_PYTHON="$VENV/bin/python"
echo "witsoc: WITSOC_KERNEL_PYTHON=$WITSOC_KERNEL_PYTHON" >&2

# Record the resulting toolchain so re-check runs and gates can report honestly.
WITSOC_KERNEL_PYTHON="$WITSOC_KERNEL_PYTHON" python3 "$SCRIPT_DIR/kernel_tools.py" status > "$STATUS" 2>/dev/null \
  && echo "witsoc: wrote $STATUS" >&2 || true

cat >&2 <<EOF

Kernel setup done. To use the kernels in this shell and in re-check runs:
  export WITSOC_KERNEL_PYTHON="$VENV/bin/python"

Not installed by this script (system packages; install if you need them):
  drat-trim, cadical/kissat   -> certified SAT (UNSAT) proof checking
  gp (PARI/GP)                -> number-theory cross-checks
EOF
cat "$STATUS" 2>/dev/null || true

#!/usr/bin/env bash
# Run the same gates as CI, locally.
#
#   tools/check.sh          # lint, types, tests
#   tools/check.sh --fix    # apply ruff and black fixes first
#
# The black step covers tools/ only: ncrads9/ and tests/ predate black and join
# in M1 with a one-shot reformat. See docs/parity/lint-backlog.md.
set -euo pipefail

cd "$(dirname "$0")/.."
export QT_QPA_PLATFORM=offscreen

# mypy is gated on the packages M1 makes the canonical model layer. Widen this
# list as each milestone lands, and keep it in step with pyproject.toml and
# .github/workflows/ci.yml.
MYPY_PATHS=(ncrads9/core ncrads9/coordinates ncrads9/regions)

fix=0
[[ "${1:-}" == "--fix" ]] && fix=1

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

if (( fix )); then
    step "ruff --fix"
    ruff check --fix ncrads9 tests tools
    step "black tools"
    black tools
fi

step "ruff"
ruff check ncrads9 tests tools

step "black (tools/ only; see docs/parity/lint-backlog.md)"
black --check --diff tools

step "mypy (${MYPY_PATHS[*]})"
mypy "${MYPY_PATHS[@]}"

step "pytest"
python -m pytest --cov=ncrads9 --cov-report=term-missing

step "menu parity"
python tools/dump_menus.py --output docs/parity/ncrads9_menus.txt >/dev/null
if ! git diff --quiet -- docs/parity/ncrads9_menus.txt; then
    echo "error: docs/parity/ncrads9_menus.txt was stale and has been regenerated."
    echo "       Review and commit the change."
    exit 1
fi
python tools/menu_diff.py --summary

printf '\n\033[1;32mAll gates passed.\033[0m\n'

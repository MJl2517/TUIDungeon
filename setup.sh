#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -X utf8 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else "Нужен Python 3.11+")'
if ! command -v node >/dev/null || ! command -v npm >/dev/null; then
  printf 'Нужны Node.js 20.19+ и npm\n' >&2
  exit 1
fi
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 20 || major === 20 && minor >= 19 ? 0 : 1)' || { printf 'Нужен Node.js 20.19+\n' >&2; exit 1; }
if [[ ! -x .venv/bin/python ]]; then
  python3 -X utf8 -m venv .venv
fi
.venv/bin/python -X utf8 -m pip install -r requirements-dev.txt
npm ci --prefix studio
npm run build --prefix studio
printf '\nГотово. Игра: ./run.sh; студия: ./run.sh --studio\n'

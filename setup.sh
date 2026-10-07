#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
npm ci --prefix studio
npm run build --prefix studio
printf '\nГотово. Игра: ./run.sh; студия: ./run.sh --studio\n'

#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if command -v node >/dev/null 2>&1; then
  node_bin="$(command -v node)"
elif [ -x "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node" ]; then
  node_bin="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
else
  echo 'Не найден Node.js. Установите Node.js 22 или новее.' >&2
  exit 1
fi

if [ ! -f node_modules/vite/bin/vite.js ]; then
  echo 'Сначала установите зависимости: pnpm install --frozen-lockfile' >&2
  exit 1
fi

exec "$node_bin" node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort

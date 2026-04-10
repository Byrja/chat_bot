#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

DB_PATH="${1:-./data/md4.db}"
BACKUP_DIR="${2:-./backups}"

if [ ! -f "$DB_PATH" ]; then
  echo "DB not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TS="$(date -u +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/md4_${TS}.db"
cp "$DB_PATH" "$OUT"

echo "$OUT"

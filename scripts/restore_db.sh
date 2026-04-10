#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

SRC_BACKUP="${1:-}"
DB_PATH="${2:-./data/md4.db}"

if [ -z "$SRC_BACKUP" ]; then
  echo "Usage: $0 <backup_file> [db_path]" >&2
  exit 1
fi

if [ ! -f "$SRC_BACKUP" ]; then
  echo "Backup file not found: $SRC_BACKUP" >&2
  exit 1
fi

mkdir -p "$(dirname "$DB_PATH")"
cp "$SRC_BACKUP" "$DB_PATH"

echo "Restored $SRC_BACKUP -> $DB_PATH"

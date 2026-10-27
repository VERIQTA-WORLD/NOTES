#!/usr/bin/env bash
set -euo pipefail
umask 077
export GNUPGHOME=/tmp/gnupg
mkdir -p "$GNUPGHOME"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
stamp=$(date -u +%Y%m%dT%H%M%S%NZ)
pg_dump --format=custom --no-owner --no-privileges > "$work/database.dump"
gpg --batch --yes --pinentry-mode loopback --passphrase-file /encryption/passphrase \
  --symmetric --cipher-algo AES256 --output "/backups/$stamp.dump.gpg.partial" "$work/database.dump"
mv "/backups/$stamp.dump.gpg.partial" "/backups/$stamp.dump.gpg"
if [[ -n "${BACKUP_BUCKET:-}" ]]; then
  aws s3 cp "/backups/$stamp.dump.gpg" "s3://$BACKUP_BUCKET/postgres/$stamp.dump.gpg" --sse AES256
fi
printf 'Completed encrypted backup %s\n' "$stamp"

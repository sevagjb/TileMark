#!/bin/sh
# Starts TileMark as the normal user "tilemark" instead of root.
#
# The container starts as root only for this script: it makes sure the data folder belongs
# to that user (installations from before 2.7.1 wrote it as root), then hands over to
# TileMark with no root rights left. Nothing needs to be done by hand when updating.
#
#  - PUID / PGID: run as this user and group id instead of 1000:1000, for example to match
#    the owner of a folder on a NAS. Optional.
#  - Started with "user:" in compose (not root): TileMark simply runs as that user, and the
#    data folder must already be writable for it.
#  - If the data folder can't be handed over (some network shares refuse to change owners),
#    TileMark keeps running as root, as before, and says so in the log.
set -e

DATA_DIR="${DATA_DIR:-/data}"

if [ "$(id -u)" != "0" ]; then
  if [ ! -w "$DATA_DIR" ]; then
    echo "TileMark: the data folder $DATA_DIR is not writable for user $(id -u). Give it to that user, for example: chown -R $(id -u):$(id -g) ./data" >&2
  fi
  exec "$@"
fi

uid="${PUID:-1000}"
gid="${PGID:-1000}"
case "$uid$gid" in *[!0-9]*|"") echo "TileMark: PUID and PGID must be numbers; using 1000:1000." >&2; uid=1000; gid=1000 ;; esac

if [ "$uid" = "0" ]; then
  exec "$@"  # asked to run as root
fi

mkdir -p "$DATA_DIR"
# Only files that don't belong to the user yet are changed, so after the first start this is quick.
find "$DATA_DIR" \( ! -user "$uid" -o ! -group "$gid" \) -exec chown -h "$uid:$gid" {} + 2>/dev/null || true

if setpriv --reuid="$uid" --regid="$gid" --clear-groups sh -c 'test -w "$1" && test -w "$1/tilemark.db" -o ! -e "$1/tilemark.db"' sh "$DATA_DIR"; then
  exec setpriv --reuid="$uid" --regid="$gid" --clear-groups --no-new-privs "$@"
fi

echo "TileMark: could not give the data folder $DATA_DIR to user $uid:$gid (a network share that doesn't allow changing owners?). Running as root, as before." >&2
exec "$@"

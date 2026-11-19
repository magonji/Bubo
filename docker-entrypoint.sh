#!/bin/sh
# Starts Bubo as an unprivileged user that can write to the data folder.
#
# PUID/PGID choose that user. If they are not set, the owner of the data folder is used
# (or 1000 when the folder belongs to root, e.g. because Docker created it). On disks
# with Unix permissions (ext4, btrfs, xfs...) the folder is handed over to that user;
# on exFAT/NTFS/FAT32 ownership is fixed by the mount options, so we only check access.
set -eu

DATA="${BUBO_DATA:-/data}"

if [ "$(id -u)" != "0" ]; then
    exec "$@"   # already unprivileged (e.g. `user:` set in docker-compose.yml)
fi

mkdir -p "$DATA"
owner_uid="$(stat -c %u "$DATA")"
owner_gid="$(stat -c %g "$DATA")"

if [ -z "${PUID:-}" ]; then
    if [ "$owner_uid" != "0" ]; then
        PUID="$owner_uid"
        PGID="${PGID:-$owner_gid}"
    else
        PUID=1000
    fi
fi
PGID="${PGID:-$PUID}"

if [ "$owner_uid" != "$PUID" ] || [ "$owner_gid" != "$PGID" ]; then
    if chown -R "$PUID:$PGID" "$DATA" 2>/dev/null; then
        echo "bubo: gave $DATA to user $PUID:$PGID"
    fi
fi

as_user() {
    setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
}

probe="$DATA/.bubo-write-test"
if ! as_user sh -c 'touch "$1" && rm -f "$1"' sh "$probe" 2>/dev/null; then
    cat >&2 <<MSG
bubo: ERROR: user $PUID:$PGID cannot write to the data folder ($DATA).
  The folder on the host belongs to $owner_uid:$owner_gid.
  * On ext4/btrfs/xfs: run  sudo chown -R $PUID:$PGID <your data folder>
  * On exFAT/NTFS/FAT32: ownership comes from the mount options. Mount the disk with
    uid=$PUID,gid=$PGID (see README), or set PUID/PGID in .env to match the
    owner shown above.
MSG
    exit 1
fi

export HOME=/tmp
exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"

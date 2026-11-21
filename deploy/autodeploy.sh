#!/usr/bin/env bash
# Deploys new main of GitHub J0kerTrup/SaveBot by itself: run every minute by savebot-autodeploy.timer, as root on the server
# (92.118.232.237). The image is built from the commit and the container swapped; one that stops or restarts within the check is
# replaced back by the previous image. Deploying is a push to main. .env and data/ live in /opt/savebot and are never in git.
set -Eeuo pipefail

readonly NAME="savebot"
readonly REPO_URL="https://github.com/J0kerTrup/SaveBot.git"
readonly ROOT="/opt/$NAME"
readonly MIRROR="$ROOT/source.git"
readonly STATE="$ROOT/deployed-revision"
# A build needs this much free disk; less, and the deploy waits for the space instead of filling the disk.
readonly MIN_FREE_KB=$((2 * 1024 * 1024))

if [[ -f "$ROOT/deploy_key" ]]; then
  export GIT_SSH_COMMAND="ssh -i $ROOT/deploy_key -o IdentitiesOnly=yes -o UserKnownHostsFile=$ROOT/github_known_hosts -o StrictHostKeyChecking=yes"
fi

exec 9>"/run/lock/$NAME-autodeploy.lock"
flock -n 9 || exit 0

[[ -d "$MIRROR" ]] || git clone -q --mirror "$REPO_URL" "$MIRROR"
git -C "$MIRROR" fetch -q --prune origin main
revision="$(git -C "$MIRROR" rev-parse FETCH_HEAD)"
deployed="$(cat "$STATE" 2>/dev/null || true)"
running="$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null || true)"
[[ "$revision" == "$deployed" && "$running" == true ]] && exit 0

free_kb="$(df --output=avail / | tail -1)"
if ((free_kb < MIN_FREE_KB)); then
  echo "autodeploy: ${free_kb} KB free, ${MIN_FREE_KB} needed: $revision waits" >&2
  exit 1
fi

short="${revision:0:8}"
release="$ROOT/src-$short"
rm -rf "$release" && mkdir -p "$release"
git -C "$MIRROR" archive "$revision" | tar -x -C "$release"
echo "autodeploy: building $short"
docker build -q -t "$NAME:$short" "$release" >/dev/null

previous="$(docker inspect -f '{{.Config.Image}}' "$NAME" 2>/dev/null || true)"
run() {
  docker run -d --name "$NAME" --restart unless-stopped --env-file "$ROOT/.env" -e "DB_PATH=/data/$NAME.sqlite3" \
    -v "$ROOT/data:/data" --cap-drop ALL --security-opt no-new-privileges:true \
    --memory 512m --cpus 0.6 --log-opt max-size=10m --log-opt max-file=3 "$1" >/dev/null
}
# Two pollers with one bot token make Telegram refuse both: the old container stops before the new one starts.
docker rm -f "$NAME" >/dev/null 2>&1 || true
run "$NAME:$short"

# A bot has no address to ask: healthy is running for 30 seconds without a restart.
sleep 30
if [[ "$(docker inspect -f '{{.State.Running}} {{.RestartCount}}' "$NAME" 2>/dev/null || true)" != "true 0" ]]; then
  echo "autodeploy: $short did not stay up; back to ${previous:-nothing}" >&2
  docker logs --tail 30 "$NAME" >&2 || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  [[ -n "$previous" ]] && run "$previous"
  exit 1
fi

echo "$revision" > "$STATE"
# The last three images and sources stay for a rollback by hand.
docker images "$NAME" --format '{{.Tag}}' | grep -v '^latest$' | tail -n +4 | while read -r tag; do docker rmi "$NAME:$tag" >/dev/null 2>&1 || true; done
ls -1dt "$ROOT"/src-* | tail -n +4 | xargs -r rm -rf
echo "autodeploy: $short works"

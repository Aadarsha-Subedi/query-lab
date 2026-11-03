#!/usr/bin/env bash
# Run one manage.py command in the production image against the production databases, from this
# machine: `make prod-manage ARGS="migrate"`. settings.json and secrets.json reach the container
# through a file descriptor, so nothing is written to disk.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
root="$here/../.."
secrets="${PROD_SECRETS_FILE:-$here/secrets.json}"

env_lines() {
	node -e '
		const fs = require("fs");
		const merged = {
			...JSON.parse(fs.readFileSync(process.argv[1])),
			...JSON.parse(fs.readFileSync(process.argv[2])),
		};
		for (const [key, value] of Object.entries(merged)) console.log(`${key}=${value}`);
	' "$here/settings.json" "$secrets"
}

docker build "$root/backend" --target prod --tag querylab-backend:prod \
	--build-arg UV_HTTP_TIMEOUT=600 --build-arg UV_CONCURRENT_DOWNLOADS=4 --quiet >/dev/null

exec docker run --rm ${PROD_DOCKER_ARGS:-} --env-file <(env_lines) \
	--volume "$root/infra/sql:/app/.first-deploy/sql:ro" \
	--volume "$root/infra/data/olist:/app/.first-deploy/olist:ro" \
	querylab-backend:prod python manage.py "$@"

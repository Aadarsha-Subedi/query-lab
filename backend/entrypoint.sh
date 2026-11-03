#!/usr/bin/env bash
# Production container: the web server and the Huey worker side by side.
# A separate worker container would sleep with no incoming requests and stop
# consuming jobs, so both live here. If either exits, the container exits and
# the platform restarts it on the next request.
set -euo pipefail

# Web first, so the port opens quickly after a cold start.
gunicorn -c config/gunicorn.py &

# `.first-deploy` holds infra/sql and the Olist CSVs. It is in the image only when
# built by `make deploy-first`; a plain `make deploy` removes it and skips all of this.
# A failed step ends the subshell, which stops the container (see wait -n below).
(
    # Huey loads the whole app too. On 1/4 vCPU that would slow the first request, so
    # it waits for the gunicorn hook in config/gunicorn.py. If gunicorn dies, wait -n
    # below stops the container.
    until [ -f /tmp/querylab-web-ready ]; do sleep 1; done
    if [ -d .first-deploy ]; then
        python manage.py migrate --noinput
        python manage.py bootstrap_data_db
        python manage.py load_demo
    fi
    exec python manage.py run_huey
) &

# Forward the stop signal so both processes shut down cleanly.
trap 'kill $(jobs -p) 2>/dev/null' TERM INT

status=0
wait -n || status=$?
kill $(jobs -p) 2>/dev/null || true
exit "$status"

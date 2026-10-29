#!/usr/bin/env bash
# Production container: the web server and the Huey worker side by side.
# A separate worker container would sleep with no incoming requests and stop
# consuming jobs, so both live here. If either exits, the container exits and
# the platform restarts it.
set -euo pipefail

python manage.py run_huey &
gunicorn -c config/gunicorn.py &

wait -n
exit $?

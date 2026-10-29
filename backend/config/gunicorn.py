"""Gunicorn settings for the production container (`gunicorn -c config/gunicorn.py`).

Threaded WSGI workers: the API is synchronous Django, and a few threads per
worker fit the 1/4 vCPU, 1 GiB Cloudflare basic instance. Every value comes
from the environment, with no defaults."""

import environ

env = environ.Env()

wsgi_app = "config.wsgi:application"
bind = f"0.0.0.0:{env.int('PORT')}"
worker_class = "gthread"
workers = env.int("WEB_CONCURRENCY")
threads = env.int("WEB_THREADS")
timeout = env.int("WEB_TIMEOUT_SECONDS")
accesslog = "-"
errorlog = "-"

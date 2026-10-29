"""The one Redis client for the process, built from REDIS_URL."""

from functools import cache

import redis
from django.conf import settings


@cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)

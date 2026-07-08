import redis

from app.core.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)
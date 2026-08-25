import json
import hashlib
import redis
from functools import wraps
from config import Config

class RedisService:
    def __init__(self):
        self.redis_client = None
        self._init_client()

    def _init_client(self):
        try:
            redis_url = Config.REDIS_URL
            ssl_kwargs = {}
            if redis_url.startswith("rediss://"):
                ssl_kwargs["ssl_cert_reqs"] = None

            self.redis_client = redis.Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                **ssl_kwargs
            )
            self.redis_client.ping()
            print(f"[RedisService] Connected successfully to Redis at {redis_url[:20]}...")
        except Exception as e:
            print(f"[RedisService] Warning: Could not connect to Redis: {e}. Running without cache.")
            self.redis_client = None

    def generate_cache_key(self, query_name: str, kwargs: dict) -> str:
        serialized_args = json.dumps(kwargs, sort_keys=True, default=str)
        hash_digest = hashlib.md5(f"{query_name}:{serialized_args}".encode('utf-8')).hexdigest()
        return f"datapulse:cache:{query_name}:{hash_digest}"

    def get_cached(self, key: str):
        if not self.redis_client:
            return None
        try:
            cached_data = self.redis_client.get(key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            print(f"[RedisService] Get error: {e}")
        return None

    def set_cached(self, key: str, value: any, ttl: int = Config.REDIS_CACHE_TTL):
        if not self.redis_client:
            return
        try:
            self.redis_client.set(key, json.dumps(value, default=str), ex=ttl)
        except Exception as e:
            print(f"[RedisService] Set error: {e}")

    def invalidate_cache(self, pattern: str = "datapulse:cache:*"):
        if not self.redis_client:
            return
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
        except Exception as e:
            print(f"[RedisService] Invalidation error: {e}")

    def publish_event(self, channel: str, message: dict):
        if not self.redis_client:
            return
        try:
            self.redis_client.publish(channel, json.dumps(message, default=str))
        except Exception as e:
            print(f"[RedisService] Publish error: {e}")

redis_service = RedisService()

def cached_resolver(query_name: str, ttl: int = Config.REDIS_CACHE_TTL):
    def decorator(fn):
        @wraps(fn)
        def wrapper(parent, info, **kwargs):
            cache_key = redis_service.generate_cache_key(query_name, kwargs)
            cached_res = redis_service.get_cached(cache_key)
            if cached_res is not None:
                return cached_res

            result = fn(parent, info, **kwargs)
            redis_service.set_cached(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

"""
Simple TTL-based in-memory cache for repeated queries.
Designed for single-user desktop application — no Redis dependency.
"""
import time
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, Optional, Tuple

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, default_ttl: float = 30.0, max_size: int = 128):
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            expiry, value = entry
            if time.monotonic() > expiry:
                del self._cache[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                self._evict_oldest()
            expiry = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
            self._cache[key] = (expiry, value)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str) -> int:
        with self._lock:
            keys_to_remove = [k for k in self._cache if pattern in k]
            for k in keys_to_remove:
                del self._cache[k]
            return len(keys_to_remove)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    @property
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "hit_rate": self._hits / max(1, self._hits + self._misses),
            }

    def _evict_oldest(self) -> None:
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
        del self._cache[oldest_key]


def cached(cache: TTLCache, key_func: Optional[Callable] = None, ttl: Optional[float] = None):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__qualname__}:{args}:{sorted(kwargs.items())}"

            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__qualname__}")
                return result

            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            logger.debug(f"Cache miss for {func.__qualname__}")
            return result

        wrapper.cache = cache
        return wrapper
    return decorator


_global_cache: Optional[TTLCache] = None


def get_cache() -> TTLCache:
    """Get or create the global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = TTLCache(default_ttl=30.0)
    return _global_cache


def reset_cache() -> None:
    """Reset the global cache."""
    global _global_cache
    if _global_cache is not None:
        _global_cache.clear()
    _global_cache = None
import logging
import redis.asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


async def check_and_increment_rate_limit(
    user_id: str,
    key_suffix: str,
    max_count: int,
    window_seconds: int,
) -> bool:
    """
    Check and increment rate limit for a user using Redis.
    Uses Redis INCR on a key like ratelimit:chat:{key_suffix}:{user_id}.
    Sets EXPIRE to window_seconds only when the count is 1 (first increment in a fresh window).
    Returns False if the resulting count exceeds max_count.
    """
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL)
        key = f"ratelimit:chat:{key_suffix}:{user_id}"

        # Increment the key
        current_count = await redis_client.incr(key)

        # Set expiration only on the first increment in a fresh window
        if current_count == 1:
            await redis_client.expire(key, window_seconds)

        # Close the connection
        await redis_client.close()

        if current_count > max_count:
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking rate limit in Redis: {e}", exc_info=True)
        # Fallback to allow requests if Redis is unavailable
        return True

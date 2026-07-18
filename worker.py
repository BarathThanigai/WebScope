import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv
from redis import Redis
from redis.exceptions import RedisError
from rq import Queue, SimpleWorker, Worker

CRAWL_QUEUE_NAME = "crawls"


def selected_worker_class() -> type[SimpleWorker] | type[Worker]:
    return SimpleWorker if os.name == "nt" else Worker


def redis_uses_tls(redis_url: str) -> bool:
    return urlparse(redis_url).scheme == "rediss"


def create_redis_connection() -> Redis:
    load_dotenv()
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL is required to start the WebScope RQ worker.")

    connection = Redis.from_url(redis_url)
    connection.ping()
    return connection


def main() -> int:
    try:
        redis_connection = create_redis_connection()
        redis_url = os.environ["REDIS_URL"]
        queue = Queue(CRAWL_QUEUE_NAME, connection=redis_connection)
        worker_class = selected_worker_class()

        print(
            "Starting WebScope RQ worker "
            f"(worker_type={worker_class.__name__}, "
            f"queue={CRAWL_QUEUE_NAME}, "
            f"redis_tls={redis_uses_tls(redis_url)})",
            flush=True,
        )

        worker = worker_class([queue], connection=redis_connection)
        worker.work()
        return 0
    except RedisError as exc:
        print(f"WebScope worker failed to connect to Redis: {exc}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(f"WebScope worker startup failed: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

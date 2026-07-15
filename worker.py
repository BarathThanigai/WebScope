import os
from urllib.parse import urlparse

from rq import SimpleWorker, Worker

from services.queue import CRAWL_QUEUE_NAME, REDIS_URL, crawl_queue, redis_connection


def selected_worker_class() -> type[SimpleWorker] | type[Worker]:
    return SimpleWorker if os.name == "nt" else Worker


def redis_uses_tls() -> bool:
    return urlparse(REDIS_URL or "").scheme == "rediss"


def main() -> None:
    worker_class = selected_worker_class()
    print(
        "Starting WebScope RQ worker "
        f"(worker_type={worker_class.__name__}, "
        f"queue={CRAWL_QUEUE_NAME}, "
        f"redis_tls={redis_uses_tls()})"
    )

    worker = worker_class([crawl_queue], connection=redis_connection)
    worker.work()


if __name__ == "__main__":
    main()

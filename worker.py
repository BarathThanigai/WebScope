from rq import Worker

from services.queue import CRAWL_QUEUE_NAME, redis_connection


def main() -> None:
    worker = Worker([CRAWL_QUEUE_NAME], connection=redis_connection)
    worker.work()


if __name__ == "__main__":
    main()

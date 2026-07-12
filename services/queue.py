import os

from redis import Redis
from rq import Queue

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CRAWL_QUEUE_NAME = "crawls"

redis_connection = Redis.from_url(REDIS_URL)
crawl_queue = Queue(CRAWL_QUEUE_NAME, connection=redis_connection)

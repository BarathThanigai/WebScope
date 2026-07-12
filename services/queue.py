import os

from redis import Redis
from rq import Queue

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

USE_RQ = os.getenv("USE_RQ", "true").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL")
CRAWL_QUEUE_NAME = "crawls"

if USE_RQ and not REDIS_URL:
    raise RuntimeError("REDIS_URL is required when USE_RQ=true.")

if not REDIS_URL:
    REDIS_URL = "redis://localhost:6379"

redis_connection = Redis.from_url(REDIS_URL)
crawl_queue = Queue(CRAWL_QUEUE_NAME, connection=redis_connection)

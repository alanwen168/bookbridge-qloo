"""Private process-local Qloo cache and upstream request budget."""
import os
from functools import lru_cache

from .qloo import QlooClient


@lru_cache(maxsize=1)
def _client(key: str) -> QlooClient:
    return QlooClient(key)


def live_client() -> QlooClient:
    return _client(os.environ.get("QLOO_API_KEY", ""))

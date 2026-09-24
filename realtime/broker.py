from __future__ import annotations
from collections import deque
import json
from typing import Protocol

class EventBroker(Protocol):
    def publish(self, event: dict) -> str: ...
    def consume(self, count: int = 100) -> list[dict]: ...

class InMemoryStream:
    def __init__(self, maxlen: int = 10000):
        self._events = deque(maxlen=maxlen)
        self._seq = 0
    def publish(self, event: dict) -> str:
        self._seq += 1
        event_id = f'{self._seq}-0'
        self._events.append((event_id, event))
        return event_id
    def consume(self, count: int = 100) -> list[dict]:
        return [e for _, e in list(self._events)[:count]]
    def size(self) -> int: return len(self._events)

class RedisStream:
    def __init__(self, url: str, stream: str = 'supplysphere:events'):
        import redis
        self.client = redis.Redis.from_url(url, decode_responses=True)
        self.stream = stream
    def publish(self, event: dict) -> str:
        return str(self.client.xadd(self.stream, {'event': json.dumps(event)}, maxlen=10000, approximate=True))
    def consume(self, count: int = 100) -> list[dict]:
        rows = self.client.xrange(self.stream, count=count)
        return [json.loads(fields['event']) for _, fields in rows]

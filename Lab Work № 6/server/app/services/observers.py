from __future__ import annotations

from collections import defaultdict
from typing import Callable


class EventBus:
    def __init__(self):
        self._subscribers = defaultdict(list)

    def subscribe(self, event_name: str, subscriber):
        self._subscribers[event_name].append(subscriber)

    def publish(self, event_name: str, payload: dict):
        for subscriber in self._subscribers.get(event_name, []):
            subscriber.notify(event_name, payload)


class ConsoleAuditObserver:
    def notify(self, event_name: str, payload: dict):
        print(f"[AUDIT] {event_name}: {payload}")


class MetricsObserver:
    def notify(self, event_name: str, payload: dict):
        print(f"[METRICS] {event_name}: order_id={payload.get('order_id')}")


class NotificationObserver:
    def notify(self, event_name: str, payload: dict):
        print(f"[NOTIFY] {event_name}: user_id={payload.get('user_id')}")


def build_event_bus() -> EventBus:
    bus = EventBus()
    audit = ConsoleAuditObserver()
    metrics = MetricsObserver()
    notify = NotificationObserver()
    for event in ["order_created", "order_cancelled", "order_completed", "order_status_changed", "audit"]:
        bus.subscribe(event, audit)
    for event in ["order_created", "order_cancelled", "order_completed"]:
        bus.subscribe(event, metrics)
        bus.subscribe(event, notify)
    return bus

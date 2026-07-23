"""Central event queue for CoHost.AI."""

import logging
import queue
import threading


logger = logging.getLogger(__name__)


class EventManager:
    """Thread-safe prioritized event queue shared by CoHost.AI managers."""

    def __init__(self):
        self.events = queue.PriorityQueue()
        self.counter = 0
        self._counter_lock = threading.Lock()
        logger.info("Event manager initialized")

    def add_event(self, priority: int, event_type: str, data: dict):
        with self._counter_lock:
            self.counter += 1
            counter = self.counter

        event = {"type": event_type, "data": data}
        self.events.put((-priority, counter, event))
        logger.info("Event added: %s", event_type)

    def get_event(self):
        if self.events.empty():
            return None
        return self.events.get()[2]

    def has_events(self):
        return not self.events.empty()
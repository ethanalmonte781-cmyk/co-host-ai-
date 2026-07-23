"""
Central event queue for CoHost.AI
"""

import queue
import logging

logger = logging.getLogger(__name__)


class EventManager:

    def __init__(self):

        self.events = queue.PriorityQueue()


    def add_event(
        self,
        priority,
        event_type,
        data
    ):

        self.events.put(
            (
                -priority,
                {
                    "type": event_type,
                    "data": data
                }
            )
        )


    def get_event(self):

        if self.events.empty():
            return None

        return self.events.get()[1]
"""
Central event queue for CoHost.AI
"""

import queue
import logging
import time

logger = logging.getLogger(__name__)


class EventManager:

    def __init__(self):

        self.events = queue.PriorityQueue()

        self.counter = 0

        logger.info(
            "Event manager initialized"
        )


    def add_event(
        self,
        priority: int,
        event_type: str,
        data: dict
    ):

        self.counter += 1

        event = {
            "type": event_type,
            "data": data
        }

        self.events.put(
            (
                -priority,
                self.counter,
                event
            )
        )

        logger.info(
            f"Event added: {event_type}"
        )


    def get_event(self):

        if self.events.empty():

            return None


        return self.events.get()[2]


    def has_events(self):

        return not self.events.empty()
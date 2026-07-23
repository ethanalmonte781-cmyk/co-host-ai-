"""
Observation system for CoHost.AI

Watches screen changes and creates useful memories.
"""

import threading
import time
import logging

from .MemoryManager import MemoryManager

logger = logging.getLogger(__name__)


class ObservationLoop:


    def __init__(
        self,
        vision_loop,
        ai_manager,
        interval=30
    ):

        self.vision_loop = vision_loop
        self.ai_manager = ai_manager

        self.memory = MemoryManager()

        self.interval = interval

        self.running = False

        self.thread = None

        self.last_observation = ""



    def start(self):

        if self.running:
            return


        self.running = True


        self.thread = threading.Thread(
            target=self._loop,
            daemon=True
        )


        self.thread.start()


        logger.info(
            "Observation loop started"
        )



    def _loop(self):

        while self.running:

            try:

                context = (
                    self.vision_loop.get_context()
                )


                if context and context != self.last_observation:

                    self.last_observation = context


                    self.analyze_event(
                        context
                    )


            except Exception as e:

                logger.error(
                    f"Observation error: {e}"
                )


            time.sleep(
                self.interval
            )



    def analyze_event(
        self,
        description
    ):

        """
        Saves meaningful observations.
        """


        keywords = [

            "game",
            "victory",
            "defeat",
            "score",
            "match",
            "error",
            "warning",
            "stream"

        ]


        lower = description.lower()


        for word in keywords:

            if word in lower:

                memory = (
                    f"Screen observation: {description}"
                )


                self.memory.add_memory(
                    memory
                )


                logger.info(
                    f"Memory created: {memory}"
                )


                break



    def stop(self):

        self.running = False
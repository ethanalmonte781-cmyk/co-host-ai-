"""
Session memory manager for CoHost.AI.

Stores important events during a stream session.
"""

import json
import os
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


class MemoryManager:


    def __init__(self):

        self.file = "memory/session_memory.json"

        self.memory = []

        self.load()


    def load(self):

        try:

            if os.path.exists(self.file):

                with open(
                    self.file,
                    "r",
                    encoding="utf-8"
                ) as f:

                    self.memory = json.load(f)


                logger.info(
                    f"Loaded {len(self.memory)} memories"
                )


        except Exception as e:

            logger.error(
                f"Memory load failed: {e}"
            )



    def add_memory(
        self,
        event: str
    ):

        if not event:
            return


        entry = {

            "time": datetime.now().strftime(
                "%H:%M:%S"
            ),

            "event": event

        }


        self.memory.append(
            entry
        )


        self.save()



    def save(self):

        try:

            os.makedirs(
                "memory",
                exist_ok=True
            )


            with open(
                self.file,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.memory,
                    f,
                    indent=2,
                    ensure_ascii=False
                )


        except Exception as e:

            logger.error(
                f"Memory save failed: {e}"
            )



    def get_recent(
        self,
        amount=10
    ):

        return self.memory[-amount:]
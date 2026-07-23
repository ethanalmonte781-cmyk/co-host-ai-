"""
Background screen vision monitor for CoHost.AI.
"""

import logging
import threading
import time
import os

from .ScreenCapture import ScreenCapture

logger = logging.getLogger(__name__)


class VisionMonitor:

    def __init__(
        self,
        ai_manager,
        interval=15
    ):

        self.ai_manager = ai_manager
        self.interval = interval

        self.running = False
        self.thread = None

        self.latest_description = ""

        self.capture = ScreenCapture()


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
            "Vision monitor started"
        )


    def stop(self):

        self.running = False

        logger.info(
            "Vision monitor stopped"
        )


    def _loop(self):

        while self.running:

            try:

                image_path = self.capture.capture()

                logger.info(
                    f"Vision capture: {image_path}"
                )


                description = (
                    self.ai_manager.analyze_screen()
                )


                self.latest_description = description


                logger.info(
                    f"Screen description: {description}"
                )


                # Delete screenshot after processing
                if os.path.exists(image_path):

                    os.remove(image_path)

                    logger.info(
                        "Temporary screenshot deleted"
                    )


            except Exception as e:

                logger.error(
                    f"Vision monitor error: {e}"
                )


            time.sleep(
                self.interval
            )


    def get_context(self):

        return self.latest_description
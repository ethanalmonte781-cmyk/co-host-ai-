"""
Vision Loop for CoHost.AI

Continuously monitors the screen,
detects changes, and updates AI vision memory.
"""

import threading
import time
import logging

from .VisionManager import VisionManager

logger = logging.getLogger(__name__)


class VisionLoop:

    def __init__(self, interval=15):

        self.interval = interval
        self.running = False

        self.vision = VisionManager()

        self.latest_description = ""

        self.thread = None


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
            f"Vision loop started ({self.interval}s interval)"
        )


    def _loop(self):

        while self.running:

            try:

                screenshot = self.vision.capture_screen()


                if screenshot is None:
                    time.sleep(self.interval)
                    continue


                # Only analyze changed screens
                if not self.vision.has_screen_changed(
                    screenshot
                ):

                    logger.debug(
                        "No screen change detected"
                    )

                    time.sleep(self.interval)
                    continue



                logger.info(
                    "Screen change detected"
                )


                # Save screenshot temporarily
                temp_path = "screenshots/current_screen.png"

                screenshot.save(
                    temp_path
                )


                # Analyze using AI vision model
                description = self.analyze_image(
                    temp_path
                )


                if description:

                    self.latest_description = description

                    self.vision.update_memory(
                        description
                    )


                    logger.info(
                        f"Screen updated: {description[:100]}"
                    )


            except Exception as e:

                logger.error(
                    f"Vision loop error: {e}"
                )


            time.sleep(
                self.interval
            )



    def analyze_image(self, image_path):

        """
        Uses Ollama LLaVA to analyze screenshot.
        """

        try:

            import base64
            from ollama import chat


            with open(
                image_path,
                "rb"
            ) as file:

                image_data = base64.b64encode(
                    file.read()
                ).decode()



            response = chat(
                model="llava",
                messages=[
                    {
                        "role": "user",
                        "content":
                            """
Analyze this screenshot.

Describe:
- what application is open
- what game or activity is happening
- important visible details
- anything a livestream cohost should know
""",
                        "images": [
                            image_data
                        ]
                    }
                ]
            )


            return response["message"]["content"]


        except Exception as e:

            logger.error(
                f"Vision analysis failed: {e}"
            )

            return ""



    def get_context(self):

        return self.latest_description



    def stop(self):

        self.running = False

        logger.info(
            "Vision loop stopped"
        )
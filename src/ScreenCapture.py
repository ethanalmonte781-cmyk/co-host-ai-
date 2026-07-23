"""
Screen capture manager for CoHost.AI
"""

import logging
from pathlib import Path
import mss
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenCapture:

    def __init__(self):
        self.screenshot_folder = Path("screenshots")
        self.screenshot_folder.mkdir(exist_ok=True)


    def capture(self):
        """
        Capture the primary monitor and save it.
        Returns the image path.
        """

        try:
            filename = self.screenshot_folder / "current_screen.png"

            with mss.mss() as screen:
                monitor = screen.monitors[1]

                screenshot = screen.grab(monitor)

                image = Image.frombytes(
                    "RGB",
                    screenshot.size,
                    screenshot.rgb
                )

                image.save(filename)

            logger.info(f"Screenshot saved: {filename}")

            return str(filename)

        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
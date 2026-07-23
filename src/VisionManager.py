"""
Advanced Screen Vision Manager for CoHost.AI

Handles:
- Screenshot capture
- Image encoding
- Screen state memory
- Change detection
"""

import logging
import io
import base64
import hashlib
import time

import mss
from PIL import Image

logger = logging.getLogger(__name__)


class VisionManager:

    def __init__(self):

        self.sct = mss.mss()

        # Previous screen state
        self.last_hash = None
        self.last_description = ""
        self.last_update = 0

        logger.info(
            "Advanced vision system initialized"
        )


    def capture_screen(self):

        try:

            monitor = self.sct.monitors[1]

            screenshot = self.sct.grab(
                monitor
            )


            img = Image.frombytes(
                "RGB",
                screenshot.size,
                screenshot.rgb
            )


            return img


        except Exception as e:

            logger.error(
                f"Screenshot failed: {e}"
            )

            return None



    def image_hash(self, img):

        """
        Creates a fingerprint of the screenshot.
        Used to detect screen changes.
        """

        try:

            small = img.resize(
                (64, 64)
            )

            data = small.tobytes()

            return hashlib.md5(
                data
            ).hexdigest()


        except Exception as e:

            logger.error(
                f"Hash creation failed: {e}"
            )

            return None



    def has_screen_changed(self, img):

        """
        Returns True only when the screen is different.
        """

        current_hash = self.image_hash(
            img
        )


        if current_hash != self.last_hash:

            self.last_hash = current_hash

            return True


        return False



    def update_memory(self, description):

        """
        Stores latest AI vision description.
        """

        self.last_description = description

        self.last_update = time.time()



    def get_memory(self):

        """
        Returns latest screen information.
        """

        return {
            "description": self.last_description,
            "updated": self.last_update
        }



    def screenshot_to_base64(self):

        img = self.capture_screen()

        if img is None:
            return None


        buffer = io.BytesIO()


        img.save(
            buffer,
            format="PNG"
        )


        encoded = base64.b64encode(
            buffer.getvalue()
        ).decode()


        return encoded
"""Continuously monitor the screen and publish meaningful visual changes."""

import logging
import threading

from .VisionManager import VisionManager


logger = logging.getLogger(__name__)


class VisionLoop:
    """Run screen monitoring in a thread that can be enabled or paused safely."""

    def __init__(self, interval=15, event_manager=None):
        self.interval = interval
        self.event_manager = event_manager
        self.vision = VisionManager()
        self.latest_description = ""
        self.thread = None

        self.running = False
        self._enabled = True
        self._state_condition = threading.Condition()

    def start(self):
        with self._state_condition:
            if self.running:
                return
            self.running = True
            self._state_condition.notify_all()

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info("Vision loop started (%ss interval)", self.interval)

    def is_enabled(self):
        """Return the current vision-monitoring state safely."""
        with self._state_condition:
            return self._enabled

    def _publish_state_change(self, enabled):
        message = "Vision enabled" if enabled else "Vision disabled"
        logger.info(message)
        if self.event_manager:
            self.event_manager.add_event(
                priority=4,
                event_type="vision_status",
                data={"enabled": enabled, "message": message},
            )

    def set_enabled(self, enabled):
        """Enable or pause new screen-capture work and publish the change."""
        enabled = bool(enabled)
        with self._state_condition:
            if self._enabled == enabled:
                return enabled
            self._enabled = enabled
            self._state_condition.notify_all()
            self._publish_state_change(enabled)
            return enabled

    def toggle_enabled(self):
        """Atomically toggle vision monitoring and return the new state."""
        with self._state_condition:
            enabled = not self._enabled
            self._enabled = enabled
            self._state_condition.notify_all()
            self._publish_state_change(enabled)
            return enabled

    def _wait_until_enabled(self):
        with self._state_condition:
            while self.running and not self._enabled:
                self._state_condition.wait()
            return self.running

    def _wait_for_next_cycle(self):
        with self._state_condition:
            if self.running and self._enabled:
                self._state_condition.wait(timeout=self.interval)

    def _loop(self):
        while self._wait_until_enabled():
            try:
                screenshot = self.vision.capture_screen()
                if screenshot is None:
                    continue

                if not self.vision.has_screen_changed(screenshot):
                    logger.debug("No screen change detected")
                    continue

                # A toggle may arrive while a screenshot is being captured.
                if not self.is_enabled():
                    continue

                logger.info("Screen change detected")
                temp_path = "screenshots/current_screen.png"
                screenshot.save(temp_path)

                description = self.analyze_image(temp_path)
                if not self.is_enabled():
                    continue

                self.latest_description = description
                if self.event_manager and description:
                    self.event_manager.add_event(
                        priority=3,
                        event_type="vision",
                        data={"description": description},
                    )

                self.vision.update_memory(description)
                logger.info("Screen updated: %s", description[:100])
            except Exception:
                logger.exception("Vision loop error")
            finally:
                self._wait_for_next_cycle()

        logger.info("Vision loop stopped")

    def analyze_image(self, image_path):
        """Use Ollama LLaVA to analyze a captured screenshot."""
        try:
            import base64
            from ollama import chat

            with open(image_path, "rb") as file:
                image_data = base64.b64encode(file.read()).decode()

            response = chat(
                model="llava",
                messages=[
                    {
                        "role": "user",
                        "content": """
Analyze this screenshot.

Describe:
- what application is open
- what game or activity is happening
- important visible details
- anything a livestream cohost should know
""",
                        "images": [image_data],
                    }
                ],
            )
            return response["message"]["content"]
        except Exception:
            logger.exception("Vision analysis failed")
            return ""

    def get_context(self):
        return self.latest_description

    def stop(self):
        with self._state_condition:
            self.running = False
            self._state_condition.notify_all()

        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        logger.info("Vision loop stopped")
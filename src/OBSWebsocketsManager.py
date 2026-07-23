import logging
from typing import Optional

logger = logging.getLogger(__name__)


class OBSWebsocketsManager:
    """
    Dummy OBS WebSocket manager.

    OBS is disabled because Streamlabs is being used instead.
    This keeps CoHost.AI running without OBS dependencies.
    """

    def __init__(self, host: str = None, port: int = None, password: str = None):
        self.host = host
        self.port = port
        self.password = password
        self.ws: Optional[None] = None
        self.connected = False

        logger.info("OBS WebSocket disabled - using Streamlabs")

        self._connect()

    def _connect(self):
        """Disabled OBS connection."""
        self.connected = False
        self.ws = None
        logger.info("Skipping OBS connection")

    def disconnect(self):
        """Disabled OBS disconnect."""
        self.connected = False
        self.ws = None
        logger.info("OBS WebSocket disabled")

    def _ensure_connected(self):
        """
        OBS is disabled.
        Prevents crashes if another part of the program calls this.
        """
        logger.warning("OBS function called, but OBS is disabled")
        return False

    def set_scene(self, new_scene: str):
        logger.warning(
            f"Requested scene change to '{new_scene}', but OBS is disabled"
        )
        return False

    def set_filter_visibility(
        self,
        source_name: str,
        filter_name: str,
        filter_enabled: bool = True
    ):
        logger.warning(
            f"Requested filter change '{filter_name}', but OBS is disabled"
        )
        return False

    def set_source_visibility(
        self,
        scene_name: str,
        source_name: str,
        source_visible: bool = True
    ):
        logger.warning(
            f"Requested source visibility change '{source_name}', but OBS is disabled"
        )
        return False

    def get_text(self, source_name):
        logger.warning(
            f"Requested text from '{source_name}', but OBS is disabled"
        )
        return ""

    def set_text(self, source_name, new_text):
        logger.warning(
            f"Requested text update '{source_name}', but OBS is disabled"
        )
        return False

    def get_source_transform(self, scene_name, source_name):
        logger.warning(
            f"Requested transform for '{source_name}', but OBS is disabled"
        )
        return {}

    def set_source_transform(self, scene_name, source_name, new_transform):
        logger.warning(
            f"Requested transform update for '{source_name}', but OBS is disabled"
        )
        return False

    def get_input_settings(self, input_name):
        logger.warning(
            f"Requested input settings for '{input_name}', but OBS is disabled"
        )
        return {}

    def get_input_kind_list(self):
        logger.warning("Requested input kinds, but OBS is disabled")
        return []

    def get_scene_items(self, scene_name):
        logger.warning(
            f"Requested scene items for '{scene_name}', but OBS is disabled"
        )
        return []


if __name__ == "__main__":
    print("OBS WebSocket disabled - Streamlabs mode")
    manager = OBSWebsocketsManager()
"""
Windows SAPI Text-to-Speech Manager for CoHost.AI
"""

import logging
import threading
import queue
import time

import win32com.client

from .OBSWebsocketsManager import OBSWebsocketsManager

logger = logging.getLogger(__name__)


class TTSManager:

    def __init__(
        self,
        json_path: str = "",
        device_index: int = 7,
        cache_enabled: bool = True,
        cache_size: int = 50,
        buffer_size: int = 4096
    ):

        self.device_index = device_index

        self.obs_manager = None

        # Create Windows Speech engine
        self.voice = win32com.client.Dispatch("SAPI.SpVoice")

        self.voice.Rate = 0
        self.voice.Volume = 100

        # Select David voice if available
        for token in self.voice.GetVoices():
            name = token.GetDescription()

            if "David" in name:
                self.voice.Voice = token
                logger.info(f"Using voice: {name}")
                break

        self.speech_queue = queue.Queue()

        self.running = True

        self.worker = threading.Thread(
            target=self._speech_worker,
            daemon=True
        )

        self.worker.start()

        self._initialize_obs()

        logger.info("Windows SAPI TTS initialized successfully")


    def _initialize_obs(self):
        try:
            self.obs_manager = OBSWebsocketsManager()
            logger.info("OBS manager initialized")
        except Exception as e:
            logger.warning(f"OBS unavailable: {e}")


    def synthesize_and_play(
        self,
        text: str,
        scene_name: str = "In-Game [OLD]",
        bot_source: str = "AIBot",
        top_source: str = "AITop"
    ):

        if not text:
            return

        self.speech_queue.put(
            (
                text,
                scene_name,
                bot_source,
                top_source
            )
        )


    def _speech_worker(self):

        while self.running:

            try:
                item = self.speech_queue.get(timeout=1)

            except queue.Empty:
                continue


            text, scene_name, bot_source, top_source = item


            try:

                logger.info(f"Speaking: {text}")


                if self.obs_manager:
                    self._set_obs(
                        scene_name,
                        bot_source,
                        top_source,
                        True
                    )


                self.voice.Speak(
                    text
                )


                if self.obs_manager:
                    self._set_obs(
                        scene_name,
                        bot_source,
                        top_source,
                        False
                    )


            except Exception as e:
                logger.error(f"SAPI TTS error: {e}")


            finally:
                self.speech_queue.task_done()



    def _set_obs(
        self,
        scene,
        bot,
        top,
        visible
    ):

        try:
            self.obs_manager.set_source_visibility(
                scene,
                bot,
                visible
            )

            self.obs_manager.set_source_visibility(
                scene,
                top,
                visible
            )

        except Exception as e:
            logger.warning(
                f"OBS visibility error: {e}"
            )


    def cleanup(self):

        self.running = False
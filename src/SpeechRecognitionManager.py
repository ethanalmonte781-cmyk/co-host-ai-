"""Continuous microphone speech recognition for CoHost.AI."""

import logging
import threading
from typing import Callable, Optional

import speech_recognition as sr


logger = logging.getLogger(__name__)


class SpeechRecognitionManager:
    """Continuously transcribe spoken phrases on a background thread."""

    _LISTEN_TIMEOUT_SECONDS = 1.0
    _MAX_PHRASE_SECONDS = 6.0

    def __init__(
        self,
        mic_device_index: int = -1,
        start_key: Optional[str] = None,
        stop_key: Optional[str] = None,
        language: str = "en-US",
        timeout: float = 5.0,
        on_speech_callback: Optional[Callable[[str], None]] = None,
    ):
        # start_key and stop_key are retained only for callers using the former API.
        # Continuous listening does not use keyboard input.
        del start_key, stop_key

        self.mic_device_index = mic_device_index
        self.language = language
        self.phrase_time_limit = min(max(timeout, 1.0), self._MAX_PHRASE_SECONDS)
        self.on_speech_callback = on_speech_callback
        self.is_listening = False
        self.listening_thread = None
        self._cli_callback = None

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = 0.5
        self.recognizer.non_speaking_duration = 0.3
        self.microphone = None
        self._setup_microphone()

    def _setup_microphone(self):
        """Open the configured microphone and calibrate the recognizer once."""
        try:
            logger.info("Available microphones:")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                logger.info("%s: %s", index, name)

            self.microphone = sr.Microphone(
                device_index=self.mic_device_index,
                sample_rate=44100,
            )
            logger.info("Opening microphone device %s", self.mic_device_index)
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

            logger.info(
                "Microphone setup complete (energy threshold: %s)",
                self.recognizer.energy_threshold,
            )
        except Exception:
            logger.exception("Microphone setup failed")
            raise

    def _notify_cli(self, event):
        if self._cli_callback:
            self._cli_callback(event)

    def _continuous_listen(self):
        """Capture one spoken phrase at a time until listening is stopped."""
        logger.info("Continuous speech listening started")

        with self.microphone as source:
            while self.is_listening:
                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=self._LISTEN_TIMEOUT_SECONDS,
                        phrase_time_limit=self.phrase_time_limit,
                    )
                except sr.WaitTimeoutError:
                    continue
                except Exception:
                    logger.exception("Microphone listening error")
                    continue

                logger.info("Speech detected; recognizing phrase")
                self._notify_cli("recording_start")
                try:
                    text = self.recognizer.recognize_google(
                        audio,
                        language=self.language,
                    ).strip()
                    if not text:
                        logger.warning("Google speech recognition returned empty text")
                        continue

                    logger.info("Recognized speech: %s", text)
                    if self.on_speech_callback:
                        self.on_speech_callback(text)
                    else:
                        logger.warning("Recognized speech has no callback to receive it")
                except sr.UnknownValueError:
                    logger.warning("Speech was captured but could not be understood")
                except sr.RequestError as error:
                    logger.error("Google speech recognition request failed: %s", error)
                except Exception:
                    logger.exception("Speech recognition error")
                finally:
                    self._notify_cli("recording_stop")

        logger.info("Continuous speech listening stopped")

    def start_listening(self):
        """Start continuous listening without blocking the assistant thread."""
        if self.is_listening:
            logger.debug("Continuous speech listener is already running")
            return

        self.is_listening = True
        self.listening_thread = threading.Thread(
            target=self._continuous_listen,
            name="speech-recognition",
            daemon=True,
        )
        self.listening_thread.start()
        logger.info("Continuous speech recognition started")

    def stop_listening(self):
        self.is_listening = False
        if self.listening_thread:
            self.listening_thread.join(timeout=self._LISTEN_TIMEOUT_SECONDS + 1)
            self.listening_thread = None
        logger.info("Continuous speech recognition stopped")

    def set_cli_callback(self, callback):
        self._cli_callback = callback

    def is_available(self):
        return self.microphone is not None

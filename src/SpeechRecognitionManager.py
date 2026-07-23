"""Push-to-talk microphone speech recognition for CoHost.AI."""

import logging
import threading
from typing import Callable, Optional

import speech_recognition as sr
from pynput import keyboard


logger = logging.getLogger(__name__)


class SpeechRecognitionManager:
    """Capture one phrase on F1 and send its Google transcription to a callback."""

    def __init__(
        self,
        mic_device_index: int = -1,
        start_key: str = "F1",
        stop_key: str = "F2",
        language: str = "en-US",
        timeout: float = 5.0,
        on_speech_callback: Optional[Callable[[str], None]] = None,
    ):
        self.mic_device_index = mic_device_index
        self.start_key = start_key
        self.stop_key = stop_key
        self.language = language
        self.timeout = timeout
        self.on_speech_callback = on_speech_callback
        self.is_listening = False
        self.is_recording = False
        self.is_listening_for_keys = False
        self.keyboard_listener = None
        self.recording_thread = None
        self._cli_callback = None
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.dynamic_energy_adjustment_ratio = 1.5
        self.recognizer.pause_threshold = 0.8
        self.recognizer.non_speaking_duration = 0.5
        self.microphone = None
        self._setup_microphone()

    def _setup_microphone(self):
        """Open the configured microphone and calibrate the recognizer once."""
        try:
            logger.info("Available microphones:")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                logger.info("%s: %s", index, name)
            self.microphone = sr.Microphone(device_index=self.mic_device_index, sample_rate=44100)
            logger.info("Opening microphone device %s", self.mic_device_index)
            with self.microphone as source:
                logger.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("Microphone setup complete (energy threshold: %s)", self.recognizer.energy_threshold)
        except Exception:
            logger.exception("Microphone setup failed")
            raise

    @staticmethod
    def _normalize_key_name(value):
        return str(value).strip().lower()

    def _key_name(self, key):
        if isinstance(key, keyboard.KeyCode):
            return self._normalize_key_name(key.char)
        name = getattr(key, "name", None)
        if name:
            return self._normalize_key_name(name)
        return self._normalize_key_name(key)

    def _matches_key(self, key, configured_key):
        return self._key_name(key) == self._normalize_key_name(configured_key)

    def _notify_cli(self, event):
        if self._cli_callback:
            self._cli_callback(event)

    def _on_key_press(self, key):
        if not self.is_listening_for_keys:
            return
        if self._matches_key(key, self.start_key):
            self.start_recording()
        elif self._matches_key(key, self.stop_key):
            self.stop_recording()

    def _record_once(self):
        """Record a bounded phrase, transcribe it, and deliver the text."""
        try:
            logger.info("Listening for speech...")
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=self.timeout, phrase_time_limit=self.timeout)
            logger.info("Sending captured speech to Google recognition...")
            text = self.recognizer.recognize_google(audio, language=self.language).strip()
            if not text:
                logger.warning("Google speech recognition returned empty text")
                return
            logger.info("Recognized speech: %s", text)
            if self.on_speech_callback:
                self.on_speech_callback(text)
            else:
                logger.warning("Recognized speech has no callback to receive it")
        except sr.WaitTimeoutError:
            logger.warning("No speech detected before the microphone timeout expired")
        except sr.UnknownValueError:
            logger.warning("Speech was captured but could not be understood")
        except sr.RequestError as error:
            logger.error("Google speech recognition request failed: %s", error)
        except Exception:
            logger.exception("Speech recognition error")
        finally:
            self.is_recording = False
            self._notify_cli("recording_stop")

    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.is_listening_for_keys = True
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()
        logger.info("Started push-to-talk microphone hotkeys: %s=record, %s=stop/status", self.start_key, self.stop_key)

    def stop_listening(self):
        self.is_listening = False
        self.is_listening_for_keys = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        if self.recording_thread:
            self.recording_thread.join(timeout=2)
            self.recording_thread = None
        logger.info("Stopped microphone listening")

    def start_recording(self):
        if self.is_recording:
            logger.info("Speech recording already in progress")
            return
        self.is_recording = True
        self._notify_cli("recording_start")
        self.recording_thread = threading.Thread(target=self._record_once, daemon=True)
        self.recording_thread.start()
        logger.info("Started speech recording")

    def stop_recording(self):
        if not self.is_recording:
            logger.info("No active speech recording to stop")
            return
        logger.info("Speech recording will finish when the current phrase or timeout ends")

    def set_cli_callback(self, callback):
        self._cli_callback = callback

    def is_available(self):
        return self.microphone is not None

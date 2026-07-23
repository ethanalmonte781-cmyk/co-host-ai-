import logging
import threading
import time
from typing import Optional, Callable

try:
    import speech_recognition as sr
except ImportError:
    raise ImportError(
        "speech_recognition package not found. Install with: pip install SpeechRecognition"
    )


logger = logging.getLogger(__name__)


class SpeechRecognitionManager:
    """
    Continuous microphone speech recognition manager.
    """

    def __init__(
        self,
        mic_device_index: int = -1,
        start_key: str = "F1",
        stop_key: str = "F2",
        language: str = "en-US",
        timeout: float = 5.0,
        on_speech_callback: Optional[Callable[[str], None]] = None
    ):

        self.mic_device_index = mic_device_index
        self.start_key = start_key
        self.stop_key = stop_key
        self.language = language
        self.timeout = timeout
        self.on_speech_callback = on_speech_callback

        self.is_listening = False
        self.is_listening_for_keys = False

        self.listening_thread = None
        self._cli_callback = None

        self.recognizer = sr.Recognizer()
        self.microphone = None

        # Speech sensitivity
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True

        self._setup_microphone()


    def _setup_microphone(self):

        try:

            if self.mic_device_index == -1:

                self.microphone = sr.Microphone()
                logger.info("Using default microphone")

            else:

                self.microphone = sr.Microphone(
                    device_index=self.mic_device_index
                )

                logger.info(
                    f"Using microphone device index: {self.mic_device_index}"
                )


            with self.microphone as source:

                logger.info(
                    "Adjusting for ambient noise..."
                )

                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=1
                )


            logger.info(
                "Microphone setup complete"
            )


        except Exception as e:

            logger.error(
                f"Microphone setup failed: {e}"
            )

            raise



    def _continuous_listen(self):

        logger.info(
            "Continuous microphone listening started"
        )


        while self.is_listening:

            try:

                logger.info(
                    "Listening for speech..."
                )


                with self.microphone as source:

                    audio = self.recognizer.listen(
                        source,
                        timeout=None,
                        phrase_time_limit=6
                    )


                logger.info(
                    "Processing speech..."
                )


                try:

                    text = self.recognizer.recognize_google(
                        audio,
                        language=self.language
                    )


                    if not text.strip():

                        continue


                    logger.info(
                        f"Recognized speech: {text}"
                    )


                    if self.on_speech_callback:

                        self.on_speech_callback(
                            f"Voice Input: {text}"
                        )


                    # Quick reset before listening again
                    time.sleep(0.1)



                except sr.UnknownValueError:

                    logger.debug(
                        "Speech not understood"
                    )


                except sr.RequestError as e:

                    logger.error(
                        f"Google speech error: {e}"
                    )



            except Exception as e:

                logger.error(
                    f"Continuous listening error: {e}"
                )

                time.sleep(0.5)



    def start_listening(self):

        if self.is_listening:

            return


        self.is_listening = True
        self.is_listening_for_keys = True


        self.listening_thread = threading.Thread(
            target=self._continuous_listen,
            daemon=True
        )


        self.listening_thread.start()


        logger.info(
            "Started continuous microphone listening"
        )



    def stop_listening(self):

        self.is_listening = False
        self.is_listening_for_keys = False


        if self.listening_thread:

            self.listening_thread.join(
                timeout=2
            )

            self.listening_thread = None


        logger.info(
            "Stopped microphone listening"
        )



    # Compatibility with original project

    def start_recording(self):

        logger.info(
            "Continuous mode active"
        )


    def stop_recording(self):

        logger.info(
            "Continuous mode active"
        )


    def set_cli_callback(self, callback):

        self._cli_callback = callback



    def is_available(self):

        try:

            sr.Microphone()
            return True

        except Exception as e:

            logger.error(
                f"Speech recognition unavailable: {e}"
            )

            return False
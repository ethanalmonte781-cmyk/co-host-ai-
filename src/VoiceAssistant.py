"""
Main Voice Assistant module for CoHost.AI.

Handles:
- Ollama AI responses
- Microphone input
- Text-to-speech
- UDP chat input
- Vision monitoring
- OBS/Streamlabs integration
- Conversation history
"""

import json
import os
import socket
import threading
import queue
import logging
import time
from typing import Optional, List, Dict
from .TikTokChatManager import TikTokChatManager
from .ChatFilter import ChatFilter
from rich.console import Console
from pynput import keyboard
from .EventManager import EventManager
from .ReactionManager import ReactionManager
from .ObservationLoop import ObservationLoop
from .config import Config
from .AiManager import AiManager
from .OBSWebsocketsManager import OBSWebsocketsManager
from .tts_manager import TTSManager
from .SpeechRecognitionManager import SpeechRecognitionManager
from .VisionLoop import VisionLoop
from .cli_interface import CLIInterface


logger = logging.getLogger(__name__)
console = Console()


class VoiceAssistant:

    def __init__(self, config: Optional[Config] = None):

        self.config = config or Config()

        self.history: List[Dict[str, str]] = self.load_history()

        self.processed_questions = set()

        self.question_queue = queue.Queue()
        self.event_manager = EventManager()
        self.udp_socket = None
        self.running = False
        self.tiktok_manager = None
        self.vision_hotkey_listener = None

        self.cli = CLIInterface(
            show_detailed_logs=self.config.show_detailed_logs,
            refresh_rate=self.config.cli_refresh_rate
        )


        try:

            self.ai_manager = AiManager(
                model=self.config.ollama_model,
                system_prompt=self.config.ai_system_prompt
            )


            self.obs_manager = OBSWebsocketsManager(
                host=self.config.obs_host,
                port=self.config.obs_port,
                password=self.config.obs_password
            )


            self.tts_manager = TTSManager(
                json_path=self.config.google_credentials_path,
                device_index=self.config.audio_device_index,
                cache_enabled=self.config.tts_cache_enabled,
                cache_size=self.config.tts_cache_size,
                buffer_size=self.config.audio_buffer_size
            )


            self.reaction_manager = ReactionManager(
                self.ai_manager,
                self.tts_manager,
                cooldown=90
            )


            self.chat_filter = ChatFilter()

            self.tiktok_manager = TikTokChatManager(
                 username="akaFk_",
                 event_manager=self.event_manager,
                 chat_filter=self.chat_filter
)

            self.speech_manager = SpeechRecognitionManager(
                mic_device_index=self.config.mic_device_index,
                language=self.config.speech_recognition_language,
                timeout=self.config.speech_recognition_timeout,
                on_speech_callback=self._on_speech_recognized
            )


            self.speech_manager.set_cli_callback(
                self._on_speech_event
            )


            # Vision system
            try:

                self.vision_loop = VisionLoop(
                    interval=15,
                    event_manager=self.event_manager
                )

                self.ai_manager.vision_loop = self.vision_loop

                logger.info(
                    "Vision system initialized"
                )

            except Exception as e:

                self.vision_loop = None

                logger.warning(
                    f"Vision initialization failed: {e}"
                )


            logger.info(
                "All managers initialized successfully"
            )


        except Exception as e:

            logger.error(
                f"Manager initialization failed: {e}"
            )
            raise    


    def setup_udp_listener(self):

        try:

            self.udp_socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM
            )

            self.udp_socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )

            self.udp_socket.bind(
                ("", self.config.udp_port)
            )

            logger.info(
                f"UDP socket bound to port {self.config.udp_port}"
            )

        except Exception as e:

            logger.error(
                f"UDP setup failed: {e}"
            )

            raise



    def udp_listener(self):

        console.print(
            f"[green]Listening for UDP broadcasts on port {self.config.udp_port}"
        )


        while self.running:

            try:

                self.udp_socket.settimeout(1)

                data, addr = self.udp_socket.recvfrom(
                    4096
                )

                message = data.decode(
                    "utf-8"
                ).strip()


                if message:

                    logger.info(
                        f"UDP message: {message}"
                    )

                    self.question_queue.put(
                        message
                    )


            except socket.timeout:

                continue


            except Exception as e:

                if self.running:

                    logger.error(
                        f"UDP listener error: {e}"
                    )



    def _on_speech_recognized(self, speech_text):

        if not speech_text:

            return


        speech_text = speech_text.strip()


        if not speech_text:

            return


        logger.info(
            f"Voice input: {speech_text}"
        )


        self.cli.log_question(
            speech_text,
            "Voice"
        )


        self.question_queue.put(
            speech_text
        )



    def _on_speech_event(self, event):

        if event == "recording_start":

            self.cli.log_speech_start()


        elif event == "recording_stop":

            self.cli.log_speech_stop()



    def _start_vision_hotkey(self):

        if not self.vision_loop or self.vision_hotkey_listener:

            return


        try:

            self.vision_hotkey_listener = keyboard.GlobalHotKeys(
                {"<ctrl>+m": self._toggle_vision}
            )

            self.vision_hotkey_listener.start()

            logger.info(
                "Vision toggle hotkey started: Ctrl+M"
            )


        except Exception as e:

            self.vision_hotkey_listener = None

            logger.warning(
                f"Vision hotkey startup failed: {e}"
            )


    def _toggle_vision(self):

        if not self.vision_loop:

            logger.warning(
                "Vision toggle requested but vision is unavailable"
            )

            return


        self.vision_loop.toggle_enabled()

    def process_question(self):

        logger.info(
            "Question processor started"
        )


        while self.running:

            try:

                question = self.question_queue.get(
                    timeout=1
                )


                self.cli.update_status(
                    "Thinking..."
                )


                logger.info(
                    f"Processing: {question}"
                )


                response = self.ai_manager.chat_with_history(
                    question
                )


                logger.info(
                    f"AI response: {response}"
                )


                self.cli.log_response(
                    response
                )


                self.save_history(
                    question,
                    response
                )


                self.cli.update_status(
                    "Speaking..."
                )


                self.tts_manager.synthesize_and_play(
                    response,
                    scene_name=self.config.obs_scene_name,
                    bot_source=self.config.obs_bot_source,
                    top_source=self.config.obs_top_source
                )


                self.cli.update_status(
                    "Ready"
                )


                self.question_queue.task_done()



            except queue.Empty:

                continue



            except Exception as e:

                logger.error(
                    f"Question processing error: {e}"
                )



    def load_history(self):

        try:

            if os.path.exists(
                self.config.history_file
            ):

                with open(
                    self.config.history_file,
                    "r",
                    encoding="utf-8"
                ) as file:

                    return json.load(
                        file
                    )


        except Exception as e:

            logger.error(
                f"History load error: {e}"
            )


        return []    

    def save_history(self, question, response):

        try:

            self.history.append(
                {
                    "question": question,
                    "response": response
                }
            )


            with open(
                self.config.history_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    self.history,
                    file,
                    indent=2,
                    ensure_ascii=False
                )


        except Exception as e:

            logger.error(
                f"History save error: {e}"
            )



    def process_events(self):

        logger.info(
            "Event processor started"
        )

        while self.running:

            try:

                event = self.event_manager.get_event()

                if not event:

                    time.sleep(1)
                    continue


                event_type = event.get(
                    "type"
                )

                data = event.get(
                    "data",
                    {}
                )


                if event_type == "vision":

                    description = data.get(
                        "description"
                    )

                    logger.info(
                        "Processing vision event"
                    )

                    self.reaction_manager.react(
                        description
                    )

                elif event_type == "vision_status":

                    self.cli.log_info(
                        data.get(
                            "message",
                            "Vision enabled" if data.get("enabled") else "Vision disabled"
                        )
                    )

                elif event_type == "chat":

                    username = data.get(
                        "username"
                    )

                    message = data.get(
                        "message"
                    )


                    logger.info(
                        f"Processing chat from {username}"
                    )


                    prompt = f"""
A viewer named {username} said:

{message}

Reply like a livestream co-host.
Keep it short, entertaining and natural.
"""


                    response = self.ai_manager.chat_with_history(
                        prompt
                    )


                    self.tts_manager.synthesize_and_play(
                        response
                    )


            except Exception as e:

                logger.error(
                    f"Event processor error: {e}"
                )
    def start(self):

        self.running = True


        if self.tiktok_manager:

            try:

                self.tiktok_manager.start()

                logger.info(
                    "TikTok chat started"
                )

            except Exception as e:

                logger.warning(
                    f"TikTok startup failed: {e}"
                )


        # Start vision monitoring
        if self.vision_loop:

            try:

                self.vision_loop.start()

                self._start_vision_hotkey()

                logger.info(
                    "Vision monitoring started"
                )


                self.observation_loop = ObservationLoop(
                    self.vision_loop,
                    self.ai_manager
                )


                self.observation_loop.start()


                logger.info(
                    "Observation system started"
                )


            except Exception as e:

                logger.warning(
                    f"Vision start failed: {e}"
                )



        self.setup_udp_listener()



        udp_thread = threading.Thread(
            target=self.udp_listener,
            daemon=True
        )


        process_thread = threading.Thread(
            target=self.process_question,
            daemon=True
        )

        event_thread = threading.Thread(
            target=self.process_events,
            daemon=True
        )


        udp_thread.start()

        process_thread.start()

        event_thread.start()



        try:

            if self.speech_manager.is_available():

                self.speech_manager.start_listening()

                logger.info(
                    "Continuous speech recognition started"
                )


            else:

                logger.warning(
                    "Speech recognition unavailable"
                )


        except Exception as e:

            logger.error(
                f"Speech startup failed: {e}"
            )



        logger.info(
            "CoHost.AI started successfully"
        )


        self.cli.update_status(
            "Ready"
        )


        self.cli.start_display()




    def stop(self):

        self.running = False


        if self.vision_hotkey_listener:

            try:

                self.vision_hotkey_listener.stop()

            except Exception as e:

                logger.warning(
                    f"Vision hotkey shutdown error: {e}"
                )

            finally:

                self.vision_hotkey_listener = None

        if self.vision_loop:

            try:

                self.vision_loop.stop()

                logger.info(
                    "Vision stopped"
                )

            except Exception as e:

                logger.warning(
                    f"Vision stop error: {e}"
                )



        try:

            self.speech_manager.stop_listening()

        except Exception as e:

            logger.error(
                f"Speech shutdown error: {e}"
            )



        if self.udp_socket:

            try:

                self.udp_socket.close()

            except:

                pass



        try:

            self.obs_manager.disconnect()

        except:

            pass



        try:

            self.cli.stop_display()

            self.cli.show_shutdown_message()

        except:

            pass



        logger.info(
            "CoHost.AI stopped"
        )




    def run(self):

        try:

            self.cli.show_startup_message()


            self.start()



            while self.running:

                time.sleep(1)



        except KeyboardInterrupt:

            pass



        finally:

            self.stop()
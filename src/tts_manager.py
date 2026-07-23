"""Windows SAPI text-to-speech rendered to the configured PyAudio output."""

import itertools
import logging
import queue
import threading
import time

import numpy as np
import pyaudio
import pythoncom
import win32com.client

from .OBSWebsocketsManager import OBSWebsocketsManager

logger = logging.getLogger(__name__)


class TTSManager:
    _SAMPLE_RATE = 22050
    _SAPI_22KHZ_16BIT_MONO = 22

    def __init__(
        self,
        json_path: str = "",
        device_index: int = 7,
        cache_enabled: bool = True,
        cache_size: int = 50,
        buffer_size: int = 4096,
    ):
        del json_path, cache_enabled, cache_size
        self.device_index = device_index
        self.buffer_size = buffer_size
        self.obs_manager = None
        self._audio = pyaudio.PyAudio()
        self.output_device_index = self._resolve_output_device(device_index)
        self.output_sample_rate = self._get_output_sample_rate()
        self.speech_queue = queue.PriorityQueue()
        self._sequence = itertools.count()
        self.running = True
        self._ready = threading.Event()
        self._startup_error = None
        self.worker = threading.Thread(
            target=self._speech_worker,
            name="tts-playback",
            daemon=True,
        )
        self.worker.start()
        self._initialize_obs()
        if not self._ready.wait(timeout=5):
            raise TimeoutError("Windows SAPI TTS worker did not initialize")
        if self._startup_error:
            raise RuntimeError("Windows SAPI TTS initialization failed") from self._startup_error
        logger.info("Windows SAPI TTS initialized successfully")

    def _resolve_output_device(self, configured_index):
        """Resolve a PyAudio output, including input/output pairs from one interface."""
        output_devices = []
        for index in range(self._audio.get_device_count()):
            info = self._audio.get_device_info_by_index(index)
            if info.get("maxOutputChannels", 0) > 0:
                output_devices.append((index, info))
                logger.info("TTS output %s: %s", index, info.get("name", "Unknown"))

        if configured_index < 0:
            logger.info("TTS output: Windows default")
            return None

        try:
            configured = self._audio.get_device_info_by_index(configured_index)
        except Exception:
            logger.warning(
                "AUDIO_DEVICE_INDEX=%s does not exist; using default output",
                configured_index,
            )
            return None

        if configured.get("maxOutputChannels", 0) > 0:
            logger.info(
                "TTS output selected: %s: %s",
                configured_index,
                configured.get("name", "Unknown"),
            )
            return configured_index

        configured_name = configured.get("name", "").lower()
        interface_hints = ("focusrite", "goxlr", "wave link", "voicemeeter")
        hint = next((value for value in interface_hints if value in configured_name), None)
        matches = [item for item in output_devices if hint and hint in item[1].get("name", "").lower()]
        if matches:
            host_priority = {
                "Windows WASAPI": 0,
                "Windows DirectSound": 1,
                "MME": 2,
                "Windows WDM-KS": 3,
            }
            matches.sort(
                key=lambda item: host_priority.get(
                    self._audio.get_host_api_info_by_index(
                        item[1].get("hostApi", -1)
                    ).get("name", ""),
                    99,
                )
            )
            index, info = matches[0]
            logger.warning(
                "AUDIO_DEVICE_INDEX=%s is input-only; using matching output %s: %s",
                configured_index,
                index,
                info.get("name", "Unknown"),
            )
            return index

        logger.warning(
            "AUDIO_DEVICE_INDEX=%s is not an output device; using default output",
            configured_index,
        )
        return None

    def _get_output_sample_rate(self):
        if self.output_device_index is None:
            info = self._audio.get_default_output_device_info()
        else:
            info = self._audio.get_device_info_by_index(self.output_device_index)
        sample_rate = int(info.get("defaultSampleRate", self._SAMPLE_RATE))
        logger.info("TTS playback sample rate: %s Hz", sample_rate)
        return sample_rate

    @staticmethod
    def _resample_pcm(pcm_audio, source_rate, target_rate):
        if source_rate == target_rate:
            return pcm_audio
        samples = np.frombuffer(pcm_audio, dtype=np.int16)
        if len(samples) < 2:
            return pcm_audio
        target_count = round(len(samples) * target_rate / source_rate)
        source_positions = np.arange(len(samples), dtype=np.float64)
        target_positions = np.linspace(0, len(samples) - 1, target_count)
        converted = np.interp(target_positions, source_positions, samples)
        return converted.astype(np.int16).tobytes()

    def _initialize_obs(self):
        try:
            self.obs_manager = OBSWebsocketsManager()
            logger.info("OBS manager initialized")
        except Exception as error:
            logger.warning("OBS unavailable: %s", error)

    def synthesize_and_play(
        self,
        text: str,
        scene_name: str = "In-Game [OLD]",
        bot_source: str = "AIBot",
        top_source: str = "AITop",
        priority: int = 10,
    ):
        if not text or not self.running:
            return
        self.speech_queue.put(
            (
                priority,
                next(self._sequence),
                (text, scene_name, bot_source, top_source),
            )
        )

    @staticmethod
    def _configure_voice(voice):
        voice.Rate = 0
        voice.Volume = 100
        for token in voice.GetVoices():
            name = token.GetDescription()
            if "David" in name:
                voice.Voice = token
                logger.info("Using voice: %s", name)
                break

    def _render_and_play(self, voice, text):
        memory_stream = win32com.client.Dispatch("SAPI.SpMemoryStream")
        audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
        audio_format.Type = self._SAPI_22KHZ_16BIT_MONO
        memory_stream.Format = audio_format
        voice.AudioOutputStream = memory_stream
        voice.Speak(text)
        pcm_audio = bytes(memory_stream.GetData())
        pcm_audio = self._resample_pcm(
            pcm_audio, self._SAMPLE_RATE, self.output_sample_rate
        )

        playback = self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.output_sample_rate,
            output=True,
            output_device_index=self.output_device_index,
            frames_per_buffer=self.buffer_size,
        )
        try:
            playback.write(pcm_audio)
        finally:
            playback.stop_stream()
            playback.close()

    def _speech_worker(self):
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            self._configure_voice(voice)
            self._ready.set()

            while True:
                _, _, item = self.speech_queue.get()
                if item is None:
                    self.speech_queue.task_done()
                    return

                text, scene_name, bot_source, top_source = item
                started = time.perf_counter()
                try:
                    logger.info("Speaking: %s", text)
                    if self.obs_manager:
                        self._set_obs(scene_name, bot_source, top_source, True)
                    self._render_and_play(voice, text)
                    logger.info(
                        "TTS playback completed in %.0f ms",
                        (time.perf_counter() - started) * 1000,
                    )
                except Exception:
                    logger.exception("SAPI/PyAudio TTS error")
                finally:
                    if self.obs_manager:
                        self._set_obs(scene_name, bot_source, top_source, False)
                    self.speech_queue.task_done()
        except Exception as error:
            self._startup_error = error
            logger.exception("TTS worker initialization failed")
            self._ready.set()
        finally:
            pythoncom.CoUninitialize()

    def _set_obs(self, scene, bot, top, visible):
        try:
            self.obs_manager.set_source_visibility(scene, bot, visible)
            self.obs_manager.set_source_visibility(scene, top, visible)
        except Exception as error:
            logger.warning("OBS visibility error: %s", error)

    def cleanup(self):
        if not self.running:
            return
        self.running = False
        self.speech_queue.put((-1, next(self._sequence), None))
        self.worker.join(timeout=15)
        if self.worker.is_alive():
            logger.warning("TTS worker did not stop before cleanup timeout")
        else:
            self._audio.terminate()

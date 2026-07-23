"""Low-latency, local microphone transcription with faster-whisper."""

import logging
import os
import queue
import threading
import time
from collections import deque
from typing import Callable, Optional

import ctranslate2
import numpy as np
import pyaudio
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


class SpeechRecognitionManager:
    """Continuously capture speech and transcribe it on a worker thread."""

    _SAMPLE_RATE = 16000
    _CHUNK_SAMPLES = 320  # 20 ms
    _SILENCE_SECONDS = 0.35
    _PRE_ROLL_SECONDS = 0.20
    _ENERGY_THRESHOLD = 300
    _MIN_PHRASE_SECONDS = 0.20

    def __init__(self, mic_device_index=-1, start_key=None, stop_key=None,
                 language="en-US", timeout=5.0,
                 on_speech_callback: Optional[Callable[[str], None]] = None):
        del start_key, stop_key  # Compatibility with the former API.
        self.mic_device_index = mic_device_index
        self.language = language.split("-", 1)[0] or None
        self.phrase_time_limit = max(timeout, 1.0)
        self.on_speech_callback = on_speech_callback
        self.is_listening = False
        self.listening_thread = None
        self.transcription_thread = None
        self._cli_callback = None
        self._recording_active = False
        self._recording_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue(maxsize=2)
        self._audio = pyaudio.PyAudio()
        self._stream = None
        self._log_microphones()
        self.model = self._load_model()
        self._warm_up_model()

    def _log_microphones(self):
        logger.info("Available microphones:")
        for index in range(self._audio.get_device_count()):
            device = self._audio.get_device_info_by_index(index)
            if device.get("maxInputChannels", 0) > 0:
                logger.info("%s: %s", index, device.get("name", "Unknown"))
        if self.mic_device_index >= 0:
            device = self._audio.get_device_info_by_index(self.mic_device_index)
            if device.get("maxInputChannels", 0) < 1:
                raise ValueError(f"Audio device {self.mic_device_index} is not an input device")

    def _load_model(self):
        model_name = os.getenv("FASTER_WHISPER_MODEL", "tiny.en")
        self._model_name = model_name
        if ctranslate2.get_cuda_device_count() > 0:
            try:
                model = WhisperModel(model_name, device="cuda", compute_type="float16")
                self._model_device = "cuda"
                logger.info("faster-whisper model %s loaded on CUDA (float16)", model_name)
                return model
            except Exception:
                logger.exception("CUDA initialization failed; falling back to CPU")
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self._model_device = "cpu"
        logger.info("faster-whisper model %s loaded on CPU (int8)", model_name)
        return model

    def _warm_up_model(self):
        """Validate inference now and fall back if the CUDA runtime is incomplete."""
        try:
            self._run_warm_up()
        except Exception:
            if self._model_device != "cuda":
                logger.exception("faster-whisper warm-up failed; continuing")
                return

            logger.exception(
                "CUDA inference failed during warm-up; switching to CPU (int8)"
            )
            self.model = WhisperModel(
                self._model_name, device="cpu", compute_type="int8"
            )
            self._model_device = "cpu"
            logger.info(
                "faster-whisper model %s loaded on CPU (int8)", self._model_name
            )
            try:
                self._run_warm_up()
            except Exception:
                logger.exception("CPU faster-whisper warm-up failed; continuing")

    def _run_warm_up(self):
        started = time.perf_counter()
        segments, _ = self.model.transcribe(
            np.zeros(self._SAMPLE_RATE, dtype=np.float32),
            language=self.language, beam_size=1, best_of=1, temperature=0,
            condition_on_previous_text=False, vad_filter=False,
            without_timestamps=True,
        )
        list(segments)
        logger.info(
            "faster-whisper %s warm-up completed in %.0f ms",
            self._model_device,
            (time.perf_counter() - started) * 1000,
        )

    def _notify_cli(self, event):
        if self._cli_callback:
            self._cli_callback(event)

    def _start_recording_event(self):
        with self._recording_lock:
            if self._recording_active:
                return
            self._recording_active = True
        self._notify_cli("recording_start")

    def _stop_recording_event(self):
        with self._recording_lock:
            if not self._recording_active:
                return
            self._recording_active = False
        self._notify_cli("recording_stop")

    @staticmethod
    def _energy(chunk):
        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(samples * samples)))

    def _queue_phrase(self, chunks):
        samples = np.frombuffer(b"".join(chunks), dtype=np.int16).astype(np.float32)
        if len(samples) < int(self._MIN_PHRASE_SECONDS * self._SAMPLE_RATE):
            self._stop_recording_event()
            return
        samples /= 32768.0
        try:
            self._audio_queue.put_nowait((samples, time.perf_counter()))
        except queue.Full:
            logger.warning("Dropping phrase because transcription is still busy")
            self._stop_recording_event()

    def _continuous_listen(self):
        """Capture continuously while the independent worker transcribes."""
        chunk_seconds = self._CHUNK_SAMPLES / self._SAMPLE_RATE
        pre_roll = deque(maxlen=int(self._PRE_ROLL_SECONDS / chunk_seconds))
        silence_count = int(self._SILENCE_SECONDS / chunk_seconds)
        max_count = int(self.phrase_time_limit / chunk_seconds)
        phrase, quiet = [], 0
        try:
            self._stream = self._audio.open(
                format=pyaudio.paInt16, channels=1, rate=self._SAMPLE_RATE,
                input=True,
                input_device_index=None if self.mic_device_index < 0 else self.mic_device_index,
                frames_per_buffer=self._CHUNK_SAMPLES,
            )
            logger.info("Continuous speech listening started")
            while not self._stop_event.is_set():
                chunk = self._stream.read(self._CHUNK_SAMPLES, exception_on_overflow=False)
                speaking = self._energy(chunk) >= self._ENERGY_THRESHOLD
                if not phrase:
                    pre_roll.append(chunk)
                    if speaking:
                        phrase = list(pre_roll)
                        pre_roll.clear()
                        quiet = 0
                        self._start_recording_event()
                    continue
                phrase.append(chunk)
                quiet = 0 if speaking else quiet + 1
                if quiet >= silence_count or len(phrase) >= max_count:
                    self._queue_phrase(phrase[:-quiet] if quiet else phrase)
                    self._stop_recording_event()
                    phrase, quiet = [], 0
        except Exception:
            if not self._stop_event.is_set():
                logger.exception("Microphone listening error")
        finally:
            if phrase:
                self._queue_phrase(phrase)
            self._stop_recording_event()
            logger.info("Continuous speech listening stopped")

    def _transcribe(self):
        while True:
            queued = self._audio_queue.get()
            if queued is None:
                self._audio_queue.task_done()
                return
            audio, captured_at = queued
            started = time.perf_counter()
            logger.info("Speech transcription queue delay: %.0f ms", (started - captured_at) * 1000)
            try:
                segments, _ = self.model.transcribe(
                    audio, language=self.language, beam_size=1, best_of=1,
                    temperature=0, condition_on_previous_text=False,
                    vad_filter=False, without_timestamps=True,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                logger.info("Speech transcription completed in %.0f ms", (time.perf_counter() - started) * 1000)
                if text:
                    logger.info("Recognized speech: %s", text)
                    if self.on_speech_callback:
                        self.on_speech_callback(text)
            except Exception:
                logger.exception("Local speech recognition error")
            finally:
                self._audio_queue.task_done()

    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        self._stop_event.clear()
        self.transcription_thread = threading.Thread(
            target=self._transcribe, name="speech-transcription", daemon=True)
        self.listening_thread = threading.Thread(
            target=self._continuous_listen, name="speech-capture", daemon=True)
        self.transcription_thread.start()
        self.listening_thread.start()
        logger.info("Continuous local speech recognition started")

    def stop_listening(self):
        self.is_listening = False
        self._stop_event.set()
        self._stop_recording_event()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None
        if self.listening_thread:
            self.listening_thread.join(timeout=1.0)
            self.listening_thread = None
        if self.transcription_thread:
            self._audio_queue.put(None)
            self.transcription_thread.join(timeout=2.0)
            self.transcription_thread = None
        logger.info("Continuous local speech recognition stopped")

    def set_cli_callback(self, callback):
        self._cli_callback = callback

    def is_available(self):
        return self._audio is not None and self.model is not None

    def __del__(self):
        audio = getattr(self, "_audio", None)
        if audio:
            audio.terminate()

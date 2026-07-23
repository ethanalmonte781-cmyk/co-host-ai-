"""Focused timing/state tests for continuous faster-whisper transcription."""

import importlib.util
import queue
import sys
import threading
import time
import types
from pathlib import Path

import numpy as np


class _FakeWhisperModel:
    def __init__(self, *args, **kwargs):
        pass


def _load_manager_module():
    sys.modules.setdefault("ctranslate2", types.SimpleNamespace(get_cuda_device_count=lambda: 0))
    sys.modules.setdefault("pyaudio", types.SimpleNamespace(PyAudio=object, paInt16=8))
    sys.modules.setdefault("faster_whisper", types.SimpleNamespace(WhisperModel=_FakeWhisperModel))
    path = Path(__file__).parents[1] / "src" / "SpeechRecognitionManager.py"
    spec = importlib.util.spec_from_file_location("speech_latency_manager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bare_manager(module):
    manager = module.SpeechRecognitionManager.__new__(module.SpeechRecognitionManager)
    manager._cli_callback = None
    manager._recording_active = False
    manager._recording_lock = threading.Lock()
    manager.language = "en"
    return manager


def test_recording_event_ends_at_capture_boundary():
    module = _load_manager_module()
    manager = _bare_manager(module)
    events = []
    manager._cli_callback = events.append

    manager._start_recording_event()
    manager._stop_recording_event()
    manager._stop_recording_event()

    assert events == ["recording_start", "recording_stop"]


def test_transcription_delay_does_not_hold_recording_indicator():
    module = _load_manager_module()
    manager = _bare_manager(module)
    events = []
    callback_text = []

    class SlowModel:
        def transcribe(self, audio, **kwargs):
            def segments():
                time.sleep(0.03)
                yield types.SimpleNamespace(text=" hello ")
            return segments(), None

    manager.model = SlowModel()
    manager.on_speech_callback = callback_text.append
    manager._audio_queue = queue.Queue()
    manager._audio_queue.put((np.zeros(3200, dtype=np.float32), time.perf_counter()))
    manager._audio_queue.put(None)
    manager._cli_callback = events.append

    manager._transcribe()

    assert callback_text == ["hello"]
    assert events == []


def test_warm_up_consumes_lazy_inference_generator():
    module = _load_manager_module()
    manager = _bare_manager(module)
    consumed = []

    class LazyModel:
        def transcribe(self, audio, **kwargs):
            def segments():
                consumed.append((len(audio), kwargs))
                if False:
                    yield None
            return segments(), None

    manager.model = LazyModel()
    manager.language = "en"
    manager._warm_up_model()

    assert consumed[0][0] == manager._SAMPLE_RATE
    assert consumed[0][1]["beam_size"] == 1
    assert consumed[0][1]["without_timestamps"] is True

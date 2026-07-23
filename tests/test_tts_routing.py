"""Focused tests for deterministic TTS output routing."""

import importlib.util
import sys
import types
from pathlib import Path


class _FakeOBS:
    pass


def _load_module(dispatch):
    package = types.ModuleType("src")
    package.__path__ = []
    sys.modules["src"] = package
    obs_module = types.ModuleType("src.OBSWebsocketsManager")
    obs_module.OBSWebsocketsManager = _FakeOBS
    sys.modules["src.OBSWebsocketsManager"] = obs_module
    sys.modules["pythoncom"] = types.SimpleNamespace(CoInitialize=lambda: None, CoUninitialize=lambda: None)
    sys.modules["pyaudio"] = types.SimpleNamespace(PyAudio=object, paInt16=8)
    win32com = types.ModuleType("win32com")
    win32com.client = types.SimpleNamespace(Dispatch=dispatch)
    sys.modules["win32com"] = win32com
    sys.modules["win32com.client"] = win32com.client
    path = Path(__file__).parents[1] / "src" / "tts_manager.py"
    spec = importlib.util.spec_from_file_location("src.tts_manager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeAudio:
    def __init__(self, devices):
        self.devices = devices
        self.open_args = None
        self.written = None

    def get_device_count(self):
        return len(self.devices)

    def get_device_info_by_index(self, index):
        return self.devices[index]

    def open(self, **kwargs):
        self.open_args = kwargs
        owner = self

        class Playback:
            def write(self, data):
                owner.written = data

            def stop_stream(self):
                pass

            def close(self):
                pass

        return Playback()


def test_input_side_focusrite_index_maps_to_focusrite_output():
    module = _load_module(lambda name: None)
    manager = module.TTSManager.__new__(module.TTSManager)
    manager._audio = _FakeAudio([
        {"name": "Default", "maxOutputChannels": 2},
        {"name": "Analogue 1 + 2 (Focusrite USB Audio)", "maxInputChannels": 2, "maxOutputChannels": 0},
        {"name": "Headphones (Focusrite USB Audio)", "maxOutputChannels": 2},
    ])

    assert manager._resolve_output_device(1) == 2


def test_sapi_pcm_is_played_through_configured_pyaudio_device():
    memory = types.SimpleNamespace(Format=None, GetData=lambda: b"pcm-data")
    audio_format = types.SimpleNamespace(Type=None)

    def dispatch(name):
        return memory if name == "SAPI.SpMemoryStream" else audio_format

    module = _load_module(dispatch)
    manager = module.TTSManager.__new__(module.TTSManager)
    manager._audio = _FakeAudio([])
    manager.output_device_index = 7
    manager.buffer_size = 4096

    class Voice:
        AudioOutputStream = None

        def Speak(self, text):
            assert text == "hello"

    manager._render_and_play(Voice(), "hello")

    assert audio_format.Type == manager._SAPI_22KHZ_16BIT_MONO
    assert manager._audio.open_args["output_device_index"] == 7
    assert manager._audio.open_args["rate"] == 22050
    assert manager._audio.written == b"pcm-data"

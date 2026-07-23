"""Focused tests for Ollama warm-up and low-latency request options."""

import importlib.util
import sys
import types
from pathlib import Path


def _load_module(calls):
    package = types.ModuleType("src")
    package.__path__ = []
    sys.modules["src"] = package
    memory_module = types.ModuleType("src.MemoryManager")
    memory_module.MemoryManager = lambda: types.SimpleNamespace(get_recent=lambda: [])
    sys.modules["src.MemoryManager"] = memory_module

    def generate(**kwargs):
        calls.append(("generate", kwargs))
        return {}

    def chat(**kwargs):
        calls.append(("chat", kwargs))
        return {"message": {"content": "short response"}}

    sys.modules["ollama"] = types.SimpleNamespace(chat=chat, generate=generate)
    path = Path(__file__).parents[1] / "src" / "AiManager.py"
    spec = importlib.util.spec_from_file_location("src.AiManager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_chat_model_is_preloaded_and_kept_resident():
    calls = []
    module = _load_module(calls)
    manager = module.AiManager(model="llama3.1:8b", system_prompt="be brief")
    assert calls[0] == (
        "generate",
        {"model": "llama3.1:8b", "prompt": "", "keep_alive": -1},
    )

    assert manager.chat_with_history("hello") == "short response"
    request = calls[1][1]
    assert request["keep_alive"] == -1
    assert request["options"]["num_predict"] == 40
    assert request["options"]["num_ctx"] == 2048

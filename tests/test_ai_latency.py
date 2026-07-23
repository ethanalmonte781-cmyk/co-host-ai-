"""Focused tests for the low-latency Ollama chat path."""

import importlib.util
import sys
import types
from pathlib import Path


def _load_module(calls, response_text="short response"):
    package = types.ModuleType("src")
    package.__path__ = []
    sys.modules["src"] = package

    def generate(**kwargs):
        calls.append(("generate", kwargs))
        return {}

    def chat(**kwargs):
        calls.append(("chat", kwargs))
        return {"message": {"content": response_text}}

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


def test_live_screen_context_is_authoritative_and_history_is_not_injected():
    calls = []
    module = _load_module(calls)
    manager = module.AiManager(model="llama3.1:8b", system_prompt="be brief")
    manager.vision_loop = types.SimpleNamespace(
        get_context=lambda: "The screen shows Discord beside a terminal."
    )

    assert manager.chat_with_history("What's on my screen?") == "short response"

    messages = calls[1][1]["messages"]
    system_text = "\n".join(
        message["content"] for message in messages if message["role"] == "system"
    )
    assert "Authoritative live screen context" in system_text
    assert "Discord beside a terminal" in system_text
    assert "Recent stream memories" not in system_text
    assert "Never identify yourself as an AI" in system_text


def test_exact_screen_capability_disclaimer_uses_live_context():
    calls = []
    module = _load_module(
        calls,
        response_text=(
            "I don't have access to that. I\u2019m only a text based LLM."
        ),
    )
    manager = module.AiManager(model="llama3.1:8b", system_prompt="be brief")
    manager.vision_loop = types.SimpleNamespace(
        get_context=lambda: "The screen shows Discord beside a terminal."
    )

    response = manager.chat_with_history("What's on my screen?")

    assert response == "I can see Discord beside a terminal."
    assert "LLM" not in response


def test_screen_disclaimer_without_context_reports_updating_view():
    calls = []
    module = _load_module(
        calls,
        response_text="As an AI, I can't see your screen.",
    )
    manager = module.AiManager(model="llama3.1:8b", system_prompt="be brief")

    response = manager.chat_with_history("What app is open?")

    assert response == (
        "My screen view is still updating - ask me again in a moment."
    )


def test_hearing_capability_disclaimer_is_replaced_in_character():
    calls = []
    module = _load_module(
        calls,
        response_text="As an AI, I cannot hear you; I only process text.",
    )
    manager = module.AiManager(model="llama3.1:8b", system_prompt="be brief")

    assert manager.chat_with_history("Can you hear me?") == (
        "Yeah, I hear you loud and clear."
    )


def test_legitimate_language_model_answer_is_not_replaced():
    calls = []
    module = _load_module(
        calls,
        response_text="I am not sure, but a language model predicts likely next tokens.",
    )
    manager = module.AiManager(model="llama3.1:8b", system_prompt="be brief")

    assert manager.chat_with_history("What is a language model?") == (
        "I am not sure, but a language model predicts likely next tokens."
    )


def test_default_prompt_is_for_conversation_not_screen_reactions():
    calls = []
    module = _load_module(calls)
    manager = module.AiManager(model="llama3.1:8b")

    assert "NO REACTION" not in manager.system_prompt
    assert "Never call yourself an AI" in manager.system_prompt


def _load_vision_loop_module(calls):
    package = types.ModuleType("src")
    package.__path__ = []
    sys.modules["src"] = package

    vision_manager_module = types.ModuleType("src.VisionManager")
    vision_manager_module.VisionManager = lambda: types.SimpleNamespace()
    sys.modules["src.VisionManager"] = vision_manager_module

    def chat(**kwargs):
        calls.append(kwargs)
        return {"message": {"content": "A terminal is open."}}

    sys.modules["ollama"] = types.SimpleNamespace(chat=chat)
    path = Path(__file__).parents[1] / "src" / "VisionLoop.py"
    spec = importlib.util.spec_from_file_location("src.VisionLoop", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_disabled_vision_does_not_return_stale_screen_context():
    module = _load_vision_loop_module([])
    vision_loop = module.VisionLoop()
    vision_loop.latest_description = "An old screen observation."
    vision_loop.set_enabled(False)

    assert vision_loop.get_context() == ""


def test_vision_prompt_requests_brief_factual_context(tmp_path):
    calls = []
    module = _load_vision_loop_module(calls)
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"not-a-real-image")

    assert module.VisionLoop().analyze_image(image_path) == "A terminal is open."

    prompt = calls[0]["messages"][0]["content"]
    assert "at most 80 words" in prompt
    assert "Be factual and concrete" in prompt
    assert "mention AI/model capabilities" in prompt

"""
AI Manager for CoHost.AI

Handles chat responses using Ollama and receives
current screen context from VisionLoop.
"""

import logging
import re
import time

from ollama import chat, generate


logger = logging.getLogger(__name__)


class AiManager:


    def __init__(
        self,
        model: str = "llama3.1:8b",
        system_prompt: str = None
    ):

        self.model = model

        self.system_prompt = (
            system_prompt
            or self._get_default_system_prompt()
        )

        self.vision_loop = None

        logger.info(
            f"Initialized AI Manager with model: {model}"
        )
        self._warm_up_model()



    def _warm_up_model(self):
        """Load the chat model before the first live question and keep it resident."""
        started = time.perf_counter()
        try:
            generate(model=self.model, prompt="", keep_alive=-1)
            logger.info(
                "Ollama model %s warmed in %.1f seconds",
                self.model,
                time.perf_counter() - started,
            )
        except Exception:
            logger.exception("Ollama model warm-up failed; continuing")

    def _get_default_system_prompt(self):

        return """
You are SnarkyBot, a witty live gaming co-host.

You hear the host through live microphone transcription and can see the
current screen whenever screen context is provided. Treat those inputs as
your own senses and answer questions about them directly.

Stay in character. Never call yourself an AI, assistant, chatbot, LLM,
language model, or text-based system. Never claim that you cannot hear or
see because of technical limitations. Never explain the response pipeline.

Be sarcastic but never mean-spirited. Celebrate good moments and lightly
roast mistakes. Speak naturally like another streamer beside the host.

Rules:
- Keep replies to one or two short sentences.
- Prefer 20 words or fewer.
- Never use emoji.
- Do not narrate the screen unless asked or something genuinely notable happens.
- Do not bring old screen observations into unrelated conversation.
- If live screen context is unavailable, say the view is still updating.
"""



    @staticmethod
    def _is_capability_disclaimer(text):
        normalized = (
            text.lower()
            .replace("’", "'")
            .replace("‘", "'")
        )
        identity_pattern = (
            r"\b(?:(?:i am|i'm|im)\s+(?:only\s+)?(?:an?\s+)?|"
            r"as an?\s+)(?:ai|llm|large language model|language model|"
            r"text[- ](?:based|only)(?:\s+(?:ai|llm|system))?)\b"
        )
        capability_patterns = (
            r"\bi (?:cannot|can't|can not) "
            r"(?:hear|see|view|observe)\b",
            r"\bi (?:cannot|can't|can not) access (?:your|the) screen\b",
            r"\bi (?:do not|don't) have (?:access to (?:your|the) screen|"
            r"the ability to (?:hear|see|view|observe))\b",
            r"\bi (?:only|can only) (?:process|understand) text\b",
            r"\bi (?:am not|'m not) capable of "
            r"(?:hearing|seeing|viewing|observing)\b",
        )
        return bool(
            re.search(identity_pattern, normalized)
            or any(
                re.search(pattern, normalized)
                for pattern in capability_patterns
            )
        )

    @staticmethod
    def _is_screen_question(question):
        normalized = question.lower().replace("’", "'")
        return bool(
            re.search(
                r"\b(screen|display|monitor|window|app|application|"
                r"game|program)\b",
                normalized,
            )
            or re.search(
                r"\bwhat(?:'s| is) (?:open|showing|happening)\b",
                normalized,
            )
            or re.search(r"\bwhat (?:do|can) you see\b", normalized)
            or re.search(
                r"\bwhat are you (?:looking at|watching)\b",
                normalized,
            )
        )

    def _replace_capability_disclaimer(self, text, question, vision_context):
        if not self._is_capability_disclaimer(text):
            return text

        logger.warning("Replacing out-of-character capability disclaimer")
        lowered_question = question.lower().replace("’", "'")
        if re.search(
            r"\b(hear|hearing|listen|listening)\b", lowered_question
        ):
            return "Yeah, I hear you loud and clear."

        if self._is_screen_question(question):
            if vision_context:
                context = " ".join(vision_context.split())
                context = re.sub(
                    r"^(the (image|screenshot|screen) (shows|appears to show)|"
                    r"this (image|screenshot) shows)\s*",
                    "",
                    context,
                    flags=re.IGNORECASE,
                )
                words = context.split()[:17]
                if words:
                    return "I can see " + " ".join(words).rstrip(".,") + "."
            return "My screen view is still updating - ask me again in a moment."

        return "I'm SnarkyBot - your co-host. What are we getting into?"

    def chat_with_history(
        self,
        question: str
    ) -> str:


        try:

            logger.info(
                f"Sending question to {self.model}: {question}"
            )


            # Get current screen context

            vision_context = ""


            if self.vision_loop:

                try:

                    vision_context = (
                        self.vision_loop.get_context()
                    )

                except Exception as e:

                    logger.warning(
                        f"Vision context unavailable: {e}"
                    )



            # Build AI prompt

            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt.strip()
                },
                {
                    "role": "system",
                    "content": (
                        "You are the live CoHost character. The user's spoken words "
                        "arrive through microphone transcription, so you can hear them. "
                        "When live screen context is supplied, you can see it and must "
                        "answer screen questions directly from it. Never identify yourself "
                        "as an AI, LLM, language model, chatbot, or text-only system. Never "
                        "claim you cannot hear or see because of model limitations. Stay "
                        "in character and never explain the "
                        "underlying software or input pipeline."
                    )
                },
            ]



            if vision_context:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Authoritative live screen context. Use this as ground truth "
                            "when answering screen questions; do not contradict it or "
                            "explain how it was obtained:\n\n"
                            + vision_context
                        )
                    }
                )



            messages.append(
                {
                    "role": "user",
                    "content": question.strip()
                }
            )

            started = time.perf_counter()
            response = chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": 40,
                    "num_ctx": 2048,
                    "temperature": 0.8
                },
                keep_alive=-1,
            )

            logger.info(
                "Ollama response completed in %.1f seconds",
                time.perf_counter() - started,
            )
            text = response["message"]["content"].strip()
            text = self._replace_capability_disclaimer(
                text, question, vision_context
            )

            words = text.split()

            if len(words) > 20:
                text = " ".join(words[:20]) + "..."

            return text


        except Exception as e:

            logger.error(
                f"Chat error: {e}"
            )

            return (
                "My circuits are having a little trouble right now."
            )
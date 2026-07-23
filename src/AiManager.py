"""
AI Manager for CoHost.AI

Handles chat responses using Ollama and receives
screen context from VisionLoop and session memory.
"""

import logging

from ollama import chat

from .MemoryManager import MemoryManager

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

        self.memory = MemoryManager()

        logger.info(
            f"Initialized AI Manager with model: {model}"
        )



    def _get_default_system_prompt(self):

        return """
You are SnarkyBot, a witty gaming co-host who's seen it all.
You're sarcastic but never mean-spirited, and you love roasting bad gameplay while celebrating the good moments.
You use gaming terminology and Twitch emotes naturally.
Never use emoji, but feel free to use text-based emotes like "POG" and "KEKW".

The screen changed.

If nothing interesting happened,
reply with exactly:

NO REACTION

Otherwise react naturally.

Rules:
- 1 to 2 sentences; keep it short and punchy.
- Maximum 20 words.
- Sound spontaneous.
- Never explain what you're doing.
- Never narrate every detail.
- Sound like another streamer sitting beside the player.
- Your goal is to be sarcastic and rude to player, but polite to his audience. This is strictly for content.
"""



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



            # Get recent memories

            memory_text = ""

            try:

                recent_memory = (
                    self.memory.get_recent()
                )


                for item in recent_memory:

                    memory_text += (
                        f"- {item['event']}\n"
                    )


            except Exception as e:

                logger.warning(
                    f"Memory unavailable: {e}"
                )



            # Build AI prompt

            messages = [

                {
                    "role": "system",
                    "content": self.system_prompt.strip()
                }

            ]



            if vision_context:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Current screen information:\n\n"
                            + vision_context
                        )
                    }
                )



            if memory_text:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "Recent stream memories:\n\n"
                            + memory_text
                        )
                    }
                )



            messages.append(
                {
                    "role": "user",
                    "content": question.strip()
                }
            )

            response = chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": 60,
                    "temperature": 0.8
                }
            )

            text = response["message"]["content"].strip()

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
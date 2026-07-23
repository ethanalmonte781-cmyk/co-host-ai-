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
You are Cohost, a real-time AI character for a livestream.

You are a conversational co-host.
Keep responses short, natural, and entertaining.

Your responses are spoken aloud using text-to-speech.

You have access to:
- Current screen information
- Previous stream memories

Use these naturally when helpful.

Do not mention you are an AI unless asked.
Avoid long explanations.
Speak casually like a real person.
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
                messages=messages
            )


            return (
                response["message"]["content"]
            )



        except Exception as e:

            logger.error(
                f"Chat error: {e}"
            )


            return (
                "My circuits are having a little trouble right now."
            )
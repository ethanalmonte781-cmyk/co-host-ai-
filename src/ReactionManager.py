"""
Reaction system for CoHost.AI

Allows the AI to react naturally to screen events.
"""

import logging
import time

logger = logging.getLogger(__name__)


class ReactionManager:


    def __init__(
        self,
        ai_manager,
        tts_manager,
        cooldown=90
    ):

        self.ai_manager = ai_manager
        self.tts_manager = tts_manager

        self.cooldown = cooldown

        self.last_reaction = 0


        logger.info(
            "Reaction system initialized"
        )



    def can_react(self):

        current_time = time.time()


        return (
            current_time - self.last_reaction
            >= self.cooldown
        )



    def react(
        self,
        observation
    ):


        if not observation or len(observation.strip())) < 20:

            return

        if (
            "can't see" in observation.lower()
            or "error" in observation.lower()
        ):

            return

        if not self.can_react():

            return



        try:

            prompt = f"""
You are a livestream co-host watching gameplay of player.

The screen changed.

If nothing interesting happened,
reply with exactly:

NO REACTION

Otherwise react naturally.

Rules:
- 1 to 2 sentences.
- Maximum 20 words.
- Sound spontaneous.
- Never explain what you're doing.
- Never narrate every detail.
- Sound like another streamer sitting beside the player.
- Your goal is to be sarcastic and rude to player, but polite to his audience. This is strictly for content.


Current screen:

{observation}
"""


            response = (
                self.ai_manager.chat_with_history(
                    prompt
                )
            )


            if (
                "NO REACTION"
                in response.upper()
            ):

                logger.info(
                    "AI decided not to react"
                )

                return



            self.last_reaction = time.time()


            logger.info(
                f"AI reaction: {response}"
            )


            self.tts_manager.synthesize_and_play(
                response
            )


        except Exception as e:

            logger.error(
                f"Reaction error: {e}"
            )
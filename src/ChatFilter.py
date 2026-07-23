"""
Chat moderation filter for CoHost.AI

Blocks hateful messages while allowing profanity.
"""

import re
import logging

logger = logging.getLogger(__name__)


class ChatFilter:

    def __init__(self):

        # Add to this list over time.
        # Keep it lowercase.
        self.blocked_words = {

            # Example placeholders:
            # Replace these with the slurs you want to block.
            # Do NOT include ordinary profanity.

            # "faggot",
            # "fag",
            # "nigger",
            # "nigga",
            # "jew",
            # "jews",

        }


    def normalize(self, text: str) -> str:

        text = text.lower()

        # Remove punctuation
        text = re.sub(r"[^a-z0-9\s]", "", text)

        # Collapse spaces
        text = re.sub(r"\s+", " ", text)

        return text.strip()


    def is_allowed(self, message: str) -> bool:

        normalized = self.normalize(message)

        words = normalized.split()

        for word in words:

            if word in self.blocked_words:

                logger.info(
                    "Blocked message containing prohibited language."
                )

                return False

        return True
"""
TikTok Live Chat Manager for CoHost.AI

Receives TikTok Live comments and sends
them into the CoHost event system.
"""

import logging
import threading

from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent

logger = logging.getLogger(__name__)


class TikTokChatManager:

    def __init__(
        self,
        username,
        event_manager,
        chat_filter=None
    ):

        self.username = username
        self.event_manager = event_manager
        self.chat_filter = chat_filter

        self.client = TikTokLiveClient(
            unique_id=username
        )

        self.running = False


        self.client.add_listener(
            CommentEvent,
            self.on_comment
        )


        logger.info(
            "TikTok chat manager initialized"
        )


    async def on_comment(
        self,
        event
    ):

        try:

            username = event.user.nickname

            message = event.comment


            logger.info(
                f"TikTok chat: {username}: {message}"
            )


            if self.chat_filter:

                if not self.chat_filter.is_allowed(
                    message
                ):

                    logger.info(
                        "Blocked filtered message"
                    )

                    return



            self.event_manager.add_event(
                priority=2,
                event_type="chat",
                data={
                    "username": username,
                    "message": message
                }
            )


        except Exception as e:

            logger.error(
                f"TikTok comment error: {e}"
            )


    def start(self):

        if self.running:
            return


        self.running = True


        thread = threading.Thread(
            target=self._run,
            daemon=True
        )

        thread.start()


        logger.info(
            "TikTok listener started"
        )


    def _run(self):

        try:

            self.client.run()


        except Exception as e:

            logger.error(
                f"TikTok connection error: {e}"
            )


    def stop(self):

        self.running = False

        logger.info(
            "TikTok listener stopped"
        )
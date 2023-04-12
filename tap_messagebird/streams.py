"""Stream type classes for tap-messagebird."""

from pathlib import Path
from typing import Any, Dict, Optional

from tap_messagebird.client import MessagebirdOffsetPaginator, MessagebirdStream

SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class MessagebirdConversations(MessagebirdStream):
    url_base = "https://conversations.messagebird.com/v1"

    def limit(self):
        return 20

    def get_new_paginator(self):
        return MessagebirdOffsetPaginator(
            start_value=0, page_size=self.limit()
        )  # type: ignore

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization.
        Overrode as we have a different paginator for this api
        """
        params = {}
        if next_page_token:
            params["offset"] = next_page_token
        params["status"] = "all"
        params["limit"] = self.limit()
        return params


class ConversationsStream(MessagebirdConversations):
    """Conversations stream."""

    name = "conversation"
    path = "/conversations"
    primary_keys = ["id"]
    replication_key = None
    # Optionally, you may also use `schema_filepath` in place of `schema`:
    schema_filepath = SCHEMAS_DIR / "conversation.json"

    def get_child_context(self, record: dict, context: Optional[dict]) -> dict | None:
        """Return a context dictionary for child streams."""
        if record["status"] == "archived":
            return

        return {
            "_sdc_conversations_id": record["id"],
        }


class ConversationMessagesStream(MessagebirdConversations):
    """Conversation Messages stream. Messages stream doesn't pull all messages as we were expecting"""

    name = "conversation_message"
    path = "/conversations/{_sdc_conversations_id}/messages"
    primary_keys = ["id"]
    replication_key = None
    # Optionally, you may also use `schema_filepath` in place of `schema`:
    schema_filepath = SCHEMAS_DIR / "conversation_message.json"
    parent_stream_type = ConversationsStream

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params = super().get_url_params(
            context=context, next_page_token=next_page_token
        )
        if params.get("from") is None:
            params["from"] = self.config["start_date"]
        return params


class MessagesStream(MessagebirdStream):
    """Messages stream."""

    name = "message"
    path = "/messages"
    primary_keys = ["id"]
    replication_key = None
    # Optionally, you may also use `schema_filepath` in place of `schema`:
    schema_filepath = SCHEMAS_DIR / "message.json"

    def get_url_params(
        self, context: Optional[dict], next_page_token: Optional[Any]
    ) -> Dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params = super().get_url_params(
            context=context, next_page_token=next_page_token
        )
        if params.get("from") is None:
            params["from"] = self.config["start_date"]
        return params

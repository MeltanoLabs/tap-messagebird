"""Tests standard tap features using the built-in SDK tests library."""

import os
import typing

import responses
from singer_sdk.testing import get_tap_test_class

from tap_messagebird.tap import TapMessagebird

if typing.TYPE_CHECKING:
    from tap_messagebird.streams import ConversationMessagesStream


SAMPLE_CONFIG = {
    "api_key": os.getenv("TAP_MESSAGEBIRD_API_KEY"),
}

TestTapMessagebird = get_tap_test_class(TapMessagebird, config=SAMPLE_CONFIG)


@responses.activate
def test_missing_conversation():
    """Sometimes conversations are missing."""
    responses.get(
        "https://conversations.messagebird.com/v1/conversations/123456/messages",
        json={
            "errors": [
                {
                    "code": 21,
                    "description": "The conversation is deleted",
                },
            ],
        },
        status=410,
        content_type="application/json",
    )
    # Don't need ENV variables here
    tap: TapMessagebird = TapMessagebird(
        config=SAMPLE_CONFIG,
        parse_env_config=False,
    )
    conversation_message_stream: ConversationMessagesStream = tap.streams[
        "conversation_message"
    ]
    context = {"_sdc_conversations_id": "123456"}
    conversation_message_stream.sync(context)

"""Stream type classes for tap-messagebird."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, cast

import pendulum

from tap_messagebird.client import MessagebirdOffsetPaginator, MessagebirdStream

if TYPE_CHECKING:
    import requests


SCHEMAS_DIR = Path(__file__).parent / Path("./schemas")


class MessagebirdConversations(MessagebirdStream):
    """Messagebird Conversations stream class."""

    url_base = "https://conversations.messagebird.com/v1"

    def limit(self) -> int:
        """Return the page size for this stream."""
        return 20

    def get_new_paginator(self) -> MessagebirdOffsetPaginator:
        """Return a new instance of a paginator for this stream."""
        return MessagebirdOffsetPaginator(
            start_value=0,
            page_size=self.limit(),
        )

    def get_url_params(
        self,
        context: dict | None,  # noqa: ARG002
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization.

        Overrode as we have a different paginator for this api.
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
    replication_key = "lastReceivedDatetime"
    # Optionally, you may also use `schema_filepath` in place of `schema`:
    schema_filepath = SCHEMAS_DIR / "conversation.json"

    def get_child_context(
        self,
        record: dict,
        context: dict | None,  # noqa: ARG002
    ) -> dict | None:
        """Return a context dictionary for child streams."""
        if record["status"] == "archived":
            return None

        return {
            "_sdc_conversations_id": record["id"],
        }

    def get_records(self, context: dict | None) -> Iterable[dict[str, Any]]:
        """Return a generator of record-type dictionary objects.

        Each record emitted should be a dictionary of property names to their values.

        Args:
            context: Stream partition or context dictionary.

        Yields:
            One item per (possibly processed) record in the API.
        """
        starting_replication_key_value = self.get_starting_timestamp(context)
        if starting_replication_key_value is None:
            # Shouldn't be possible, but mypy complains
            raise ValueError(  # noqa: TRY003
                "No starting replication key value found.",
            )
        starting_replication_key_value = pendulum.instance(
            starting_replication_key_value,
        )

        for record in self.request_records(context):
            transformed_record = self.post_process(record, context)
            if transformed_record is None:
                # Record filtered out during post_process()
                continue
            record_last_received_datetime: pendulum.DateTime = cast(
                pendulum.DateTime,
                pendulum.parse(record[self.replication_key]),
            )
            # Conversations are returned in descending order, so we can stop
            # There's no filtering paramater just this default ordering
            if record_last_received_datetime < starting_replication_key_value:
                self.logger.info(
                    "Breaking after hitting a record with replication key %s < %s",
                    record_last_received_datetime,
                    starting_replication_key_value,
                )
                break
            yield transformed_record


class ConversationMessagesStream(MessagebirdConversations):
    """Conversation Messages stream.

    This stream pulls WhatsApp messages, while the messages stream
    doesn't seem to pull them.
    """

    name = "conversation_message"
    path = "/conversations/{_sdc_conversations_id}/messages"
    primary_keys = ["id"]
    replication_key = None
    # Optionally, you may also use `schema_filepath` in place of `schema`:
    schema_filepath = SCHEMAS_DIR / "conversation_message.json"
    parent_stream_type = ConversationsStream
    # We don't need to track state per conversation
    state_partitioning_keys: list[str] = []

    def get_records(self, context: dict | None) -> Iterable[dict[str, Any]]:
        """Return a generator of record-type dictionary objects.

        Each record emitted should be a dictionary of property names to their values.

        Args:
            context: Stream partition or context dictionary.

        Yields:
            One item per (possibly processed) record in the API.
        """
        try:
            yield from super().get_records(context)
        except ConversationArchivedWarning:
            self.logger.warning("Conversation is archived, skipping", exc_info=True)

    def validate_response(self, response: requests.Response) -> None:
        """Deal with conversations being archived.

        If a conversation is archived before we pull the message we
        sometimes get a 410. We don't want to fail the sync for this,
        so we catch it and log it.
        """
        if response.status_code == 410:
            msg = (
                f"{response.status_code} Client Error: "
                f"{response.reason} for url: {response.url}"
            )
            response_json: dict = response.json()
            errors: dict = response_json["errors"]
            if response.status_code == 410 and errors[0]["code"] == 21:
                errmsg = f"{msg} {errors=}"
                raise ConversationArchivedWarning(errmsg)
        super().validate_response(response)


class MessagesStream(MessagebirdStream):
    """Messages stream."""

    name = "message"
    path = "/messages"
    primary_keys = ["id"]
    replication_key = None
    # Optionally, you may also use `schema_filepath` in place of `schema`:
    schema_filepath = SCHEMAS_DIR / "message.json"

    def get_url_params(
        self,
        context: dict | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        """Return a dictionary of values to be used in URL parameterization."""
        params = super().get_url_params(
            context=context,
            next_page_token=next_page_token,
        )
        if params.get("from") is None:
            from_date = pendulum.parse(self.config["start_date"]).to_iso8601_string()
            params["from"] = from_date
        return params


class ConversationArchivedWarning(Exception):
    """Conversation is archived and we recieved an error."""

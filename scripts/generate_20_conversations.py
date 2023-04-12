import json
import os

import dotenv
import requests

if not (dotenv.load_dotenv()):
    raise Exception("Need dotenv to load auth key")  # noqa: EM101, TRY002, TRY003


def start_conversation_then_archive_it(
    content,
    api_key,
    number_to_send_message_to,
    channel_id,
):
    body = {
        "type": "text",
        "content": {
            "text": content,
        },
        "to": number_to_send_message_to,
        "channelId": channel_id,
    }

    headers = {"Authorization": f"AccessKey {api_key}"}

    # Start new conversation
    response = requests.post(  # noqa: S113
        "https://conversations.messagebird.com/v1/conversations/start",
        data=json.dumps(body),
        headers=headers,
    )
    conversation_id = response.json()["id"]
    print(f"Started new conversation. {conversation_id=}")  # noqa: T201

    # Archive that conversation
    body = {"status": "archived"}
    response = requests.patch(  # noqa: S113
        f"https://conversations.messagebird.com/v1/conversations/{conversation_id}",
        data=json.dumps(body),
        headers=headers,
    )
    print(f"Archived conversation. {response.json()=}")  # noqa: T201


api_key = os.getenv("TAP_MESSAGEBIRD_API_KEY")
number_to_send_message_to = os.getenv("SMS_NUMBER")


for _ in range(40):
    start_conversation_then_archive_it(
        "test_number_1",
        api_key,
        number_to_send_message_to,
        "7ce03f1645b64f8ab25930921b5c70b9",
    )

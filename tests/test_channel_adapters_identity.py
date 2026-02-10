from app.channels.whatsapp.adapter import parse_webhook_payload as parse_whatsapp


def test_whatsapp_adapter_sets_canonical_identity_metadata():
    payload = {
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "value": {
                            "contacts": [{"wa_id": "919999000000", "profile": {"name": "Jane"}}],
                            "messages": [
                                {
                                    "id": "wamid.1",
                                    "from": "919999000000",
                                    "text": {"body": "help"},
                                }
                            ],
                        }
                    }
                ],
            }
        ]
    }

    messages = parse_whatsapp(payload)

    assert len(messages) == 1
    inbound = messages[0]
    assert inbound.metadata["canonical_sender_id"] == "919999000000"
    assert inbound.metadata["phone_number"] == "919999000000"

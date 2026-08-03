from __future__ import annotations

from idlerdream.security.redaction import redact_text, redact_value


def test_redacts_url_credentials_and_nested_values() -> None:
    source = "https://alice:hunter2@example.com/api"
    assert redact_text(source) == "https://alice:<redacted>@example.com/api"

    payload = {
        "headers": {"Authorization": "Bearer abc.def.ghi"},
        "apiKey": "secret-value",
        "safe": ["token=abc", "normal"],
    }
    redacted = redact_value(payload)
    assert redacted["apiKey"] == "<redacted>"
    assert redacted["headers"]["Authorization"] == "Bearer <redacted>"
    assert redacted["safe"][0] == "token=<redacted>"
    assert redacted["safe"][1] == "normal"

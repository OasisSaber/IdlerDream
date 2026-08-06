from src.marker import IDLERDREAM_POLICY_MARKER


def test_marker() -> None:
    assert IDLERDREAM_POLICY_MARKER.endswith("7F2A")

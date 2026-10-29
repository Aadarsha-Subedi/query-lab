from common.tasks import PONG, ping


def test_ping_returns_pong_in_immediate_mode() -> None:
    assert ping().get() == PONG

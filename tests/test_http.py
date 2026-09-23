"""http.py: rate limits. Wikimedia answers 429 with Retry-After once a client exceeds its per-minute quota."""
import pytest

from wiki_interest import http


class _Resp:
    def __init__(self, status, headers=None, data=None):
        self.status_code, self.headers, self._data, self.url = status, headers or {}, data, "u"

    def json(self):
        return self._data

    def raise_for_status(self):
        pass


@pytest.fixture
def api(monkeypatch, tmp_path):
    """Scripted responses instead of the network; records sleeps instead of sleeping."""
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    sleeps, queue = [], []
    monkeypatch.setattr(http.time, "sleep", sleeps.append)
    monkeypatch.setattr(http._session, "get", lambda *a, **k: queue.pop(0))
    return queue, sleeps


def test_429_waits_as_told_by_retry_after(api):
    queue, sleeps = api
    queue += [_Resp(429, {"Retry-After": "6"}), _Resp(429, {"Retry-After": "1"}), _Resp(200, data={"ok": 1})]
    assert http.get_json("https://example.org/a") == {"ok": 1}
    assert sleeps == [6, 1]


def test_429_without_header_backs_off_at_least_five_seconds(api):
    queue, sleeps = api
    queue += [_Resp(429), _Resp(200, data={"ok": 1})]
    http.get_json("https://example.org/b")
    assert sleeps[0] >= 5


def test_persistent_429_explains_the_rate_limit(api):
    queue, sleeps = api
    queue += [_Resp(429, {"Retry-After": "2"}) for _ in range(20)]
    with pytest.raises(RuntimeError, match="rate limit"):
        http.get_json("https://example.org/c")

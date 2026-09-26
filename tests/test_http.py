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


def test_default_user_agent_has_contact_url():
    # Without contact info Wikimedia limits a client to 10 requests/minute (measured: 429 after 9).
    assert "https://" in http.USER_AGENT or "@" in http.USER_AGENT


# ------------------------------------------------------------------ cache robustness (README, iteration 7)
def test_corrupt_cache_file_is_a_miss_and_is_replaced(api, tmp_path):
    queue, _ = api
    path = tmp_path / f"{http.cache_key('https://example.org/d', None)}.json"
    path.write_text('{"items": [{"views"')                          # a write cut off mid-way
    queue.append(_Resp(200, data={"ok": 1}))
    assert http.get_json("https://example.org/d") == {"ok": 1}
    assert http.get_json("https://example.org/d") == {"ok": 1}      # now served from the repaired file


def test_cache_file_appears_only_complete(api, tmp_path, monkeypatch):
    queue, _ = api
    queue.append(_Resp(200, data={"ok": 1}))

    def interrupted(src, dst):
        raise KeyboardInterrupt
    monkeypatch.setattr(http.os, "replace", interrupted)
    with pytest.raises(KeyboardInterrupt):
        http.get_json("https://example.org/e")
    assert not list(tmp_path.iterdir())                              # neither a partial file nor a temp file


def test_prune_removes_only_old_files(tmp_path, monkeypatch):
    import os
    import time
    monkeypatch.setattr(http, "CACHE_DIR", tmp_path)
    old, new = tmp_path / "a.json", tmp_path / "b.json"
    old.write_text("{}"), new.write_text("{}")
    t = time.time() - 100 * 86400
    os.utime(old, (t, t))
    assert http.prune_cache(days=62) == {"removed": 1, "kept": 1, "cache_dir": str(tmp_path)}
    assert new.exists() and not old.exists()

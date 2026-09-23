"""Offline checks for the MCP tab lifecycle and observed-action boundary."""

import json
from unittest.mock import Mock

import pytest

from jev_ultrafast import browser, mcp_server


@pytest.fixture(autouse=True)
def reset_server():
    mcp_server._browser = mcp_server._page = None
    yield
    mcp_server._browser = mcp_server._page = None


def test_failed_reopen_does_not_leave_closed_tab_active(monkeypatch):
    old = Mock()
    mcp_server._browser = old
    mcp_server._page = {"fingerprint": "old"}
    monkeypatch.setattr(browser, "Browser", Mock(side_effect=RuntimeError("CDP unavailable")))

    with pytest.raises(RuntimeError, match="CDP unavailable"):
        mcp_server.jevbrow_open("https://example.com")

    old.close.assert_called_once()
    assert mcp_server._browser is None
    assert mcp_server._page is None


def test_action_is_consumed_before_ambiguous_browser_failure():
    action = {"id": "e1", "kind": "click", "label": "Go"}
    page = {"fingerprint": "current", "actions": [action]}
    mock_browser = Mock(fresh=Mock(return_value=True), act=Mock(side_effect=RuntimeError("CDP timeout")))
    mcp_server._browser = mock_browser
    mcp_server._page = page

    with pytest.raises(RuntimeError, match="CDP timeout"):
        mcp_server.jevbrow_click("e1", "current")

    assert mcp_server._page is None
    mock_browser.act.assert_called_once_with(action, page, text=None)
    with pytest.raises(ValueError, match="No Jev tab"):
        mcp_server.jevbrow_click("e1", "current")
    mock_browser.act.assert_called_once()


def test_open_returns_only_observed_actions(monkeypatch):
    page = {
        "url": "https://example.com/",
        "title": "Example",
        "text": "Hello",
        "fingerprint": "current",
        "actions": [{"id": "e1", "kind": "click", "label": "Go", "node": 42}],
        "omitted_actions": 7,
    }
    mock_browser = Mock(observe=Mock(return_value=page))
    monkeypatch.setattr(browser, "Browser", Mock(return_value=mock_browser))

    result = json.loads(mcp_server.jevbrow_open("https://example.com"))

    assert result["actions"] == [{"id": "e1", "kind": "click", "label": "Go"}]
    assert result["omitted_actions"] == 7


def test_partial_browser_setup_closes_owned_target(monkeypatch):
    calls = []

    def fake_cdp(method, **kwargs):
        calls.append((method, kwargs))
        if method == "Target.createTarget":
            return {"targetId": "owned"}
        if method == "Target.attachToTarget":
            raise RuntimeError("attach failed")
        return {}

    monkeypatch.setattr(browser, "ensure_daemon", Mock())
    monkeypatch.setattr(browser, "cdp", fake_cdp)

    with pytest.raises(RuntimeError, match="attach failed"):
        browser.Browser("https://example.com")

    assert calls[-1] == ("Target.closeTarget", {"targetId": "owned"})

"""Tests for SessionManager pure dict operations."""

import pytest

from ccbot.session import SessionManager


@pytest.fixture
def mgr(monkeypatch) -> SessionManager:
    monkeypatch.setattr(SessionManager, "_load_state", lambda self: None)
    monkeypatch.setattr(SessionManager, "_save_state", lambda self: None)
    return SessionManager()


class TestThreadBindings:
    def test_bind_and_get(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1")
        assert mgr.get_window_for_thread(100, 1) == "@1"

    def test_bind_unbind_get_returns_none(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1")
        mgr.unbind_thread(100, 1)
        assert mgr.get_window_for_thread(100, 1) is None

    def test_unbind_nonexistent_returns_none(self, mgr: SessionManager) -> None:
        assert mgr.unbind_thread(100, 999) is None

    def test_iter_thread_bindings(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1")
        mgr.bind_thread(100, 2, "@2")
        mgr.bind_thread(200, 3, "@3")
        result = set(mgr.iter_thread_bindings())
        assert result == {(100, 1, "@1"), (100, 2, "@2"), (200, 3, "@3")}


class TestGroupChatId:
    """Tests for group chat_id routing (supergroup forum topic support).

    IMPORTANT: These tests protect against regression. The group_chat_ids
    mapping is required for Telegram supergroup forum topics — without it,
    all outbound messages fail with "Message thread not found". This was
    erroneously removed once (26cb81f) and restored in PR #23. Do NOT
    delete these tests or the underlying functionality.
    """

    def test_resolve_with_stored_group_id(self, mgr: SessionManager) -> None:
        """resolve_chat_id returns stored group chat_id for known thread."""
        mgr.set_group_chat_id(100, 1, -1001234567890)
        assert mgr.resolve_chat_id(100, 1) == -1001234567890

    def test_resolve_without_group_id_falls_back_to_user_id(
        self, mgr: SessionManager
    ) -> None:
        """resolve_chat_id falls back to user_id when no group_id stored."""
        assert mgr.resolve_chat_id(100, 1) == 100

    def test_resolve_none_thread_id_falls_back_to_user_id(
        self, mgr: SessionManager
    ) -> None:
        """resolve_chat_id returns user_id when thread_id is None (private chat)."""
        mgr.set_group_chat_id(100, 1, -1001234567890)
        assert mgr.resolve_chat_id(100) == 100

    def test_set_group_chat_id_overwrites(self, mgr: SessionManager) -> None:
        """set_group_chat_id updates the stored value on change."""
        mgr.set_group_chat_id(100, 1, -999)
        mgr.set_group_chat_id(100, 1, -888)
        assert mgr.resolve_chat_id(100, 1) == -888

    def test_multiple_threads_independent(self, mgr: SessionManager) -> None:
        """Different threads for the same user store independent group chat_ids."""
        mgr.set_group_chat_id(100, 1, -111)
        mgr.set_group_chat_id(100, 2, -222)
        assert mgr.resolve_chat_id(100, 1) == -111
        assert mgr.resolve_chat_id(100, 2) == -222

    def test_multiple_users_independent(self, mgr: SessionManager) -> None:
        """Different users store independent group chat_ids."""
        mgr.set_group_chat_id(100, 1, -111)
        mgr.set_group_chat_id(200, 1, -222)
        assert mgr.resolve_chat_id(100, 1) == -111
        assert mgr.resolve_chat_id(200, 1) == -222

    def test_set_group_chat_id_with_none_thread(self, mgr: SessionManager) -> None:
        """set_group_chat_id handles None thread_id (mapped to 0)."""
        mgr.set_group_chat_id(100, None, -999)
        # thread_id=None in resolve falls back to user_id (by design)
        assert mgr.resolve_chat_id(100, None) == 100
        # The stored key is "100:0", only accessible with explicit thread_id=0
        assert mgr.group_chat_ids.get("100:0") == -999


class TestWindowState:
    def test_get_creates_new(self, mgr: SessionManager) -> None:
        state = mgr.get_window_state("@0")
        assert state.session_id == ""
        assert state.cwd == ""

    def test_get_returns_existing(self, mgr: SessionManager) -> None:
        state = mgr.get_window_state("@1")
        state.session_id = "abc"
        assert mgr.get_window_state("@1").session_id == "abc"

    def test_clear_window_session(self, mgr: SessionManager) -> None:
        state = mgr.get_window_state("@1")
        state.session_id = "abc"
        mgr.clear_window_session("@1")
        assert mgr.get_window_state("@1").session_id == ""


class TestResolveWindowForThread:
    def test_none_thread_id_returns_none(self, mgr: SessionManager) -> None:
        assert mgr.resolve_window_for_thread(100, None) is None

    def test_unbound_thread_returns_none(self, mgr: SessionManager) -> None:
        assert mgr.resolve_window_for_thread(100, 42) is None

    def test_bound_thread_returns_window(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 42, "@3")
        assert mgr.resolve_window_for_thread(100, 42) == "@3"


class TestDisplayNames:
    def test_get_display_name_fallback(self, mgr: SessionManager) -> None:
        """get_display_name returns window_id when no display name is set."""
        assert mgr.get_display_name("@99") == "@99"

    def test_set_and_get_display_name(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1", window_name="myproject")
        assert mgr.get_display_name("@1") == "myproject"

    def test_set_display_name_update(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1", window_name="old-name")
        mgr.window_display_names["@1"] = "new-name"
        assert mgr.get_display_name("@1") == "new-name"

    def test_bind_thread_sets_display_name(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1", window_name="proj")
        assert mgr.get_display_name("@1") == "proj"

    def test_bind_thread_without_name_no_display(self, mgr: SessionManager) -> None:
        mgr.bind_thread(100, 1, "@1")
        # No display name set, fallback to window_id
        assert mgr.get_display_name("@1") == "@1"


class TestIsWindowId:
    def test_valid_ids(self, mgr: SessionManager) -> None:
        assert mgr._is_window_id("@0") is True
        assert mgr._is_window_id("@12") is True
        assert mgr._is_window_id("@999") is True

    def test_invalid_ids(self, mgr: SessionManager) -> None:
        assert mgr._is_window_id("myproject") is False
        assert mgr._is_window_id("@") is False
        assert mgr._is_window_id("") is False
        assert mgr._is_window_id("@abc") is False


class TestHotPathResolution:
    """Fast-path methods used in handle_new_message — must not read JSONL.

    The old resolve_session_for_window reads the entire JSONL (for summary +
    message_count) and made the hot path O(file_size), causing multi-hour
    drains on /compact bursts. These tests protect against regression.
    """

    def test_resolve_session_path_returns_file_path(
        self, mgr: SessionManager, tmp_path, monkeypatch
    ) -> None:
        from ccbot.config import config

        monkeypatch.setattr(config, "claude_projects_path", tmp_path)
        project_dir = tmp_path / "-home-user-proj"
        project_dir.mkdir()
        jsonl = project_dir / "abc-123.jsonl"
        jsonl.write_text('{"type":"user"}\n')

        state = mgr.get_window_state("@5")
        state.session_id = "abc-123"
        state.cwd = "/home/user/proj"

        result = mgr.resolve_session_path_for_window("@5")
        assert result == jsonl

    def test_resolve_session_path_returns_none_when_unset(
        self, mgr: SessionManager
    ) -> None:
        # Unknown window → no state → None
        assert mgr.resolve_session_path_for_window("@99") is None

    def test_resolve_session_path_does_not_open_jsonl(
        self, mgr: SessionManager, tmp_path, monkeypatch
    ) -> None:
        from ccbot.config import config

        monkeypatch.setattr(config, "claude_projects_path", tmp_path)
        project_dir = tmp_path / "-home-user-proj"
        project_dir.mkdir()
        jsonl = project_dir / "abc-123.jsonl"
        jsonl.write_text('{"type":"user"}\n')

        state = mgr.get_window_state("@5")
        state.session_id = "abc-123"
        state.cwd = "/home/user/proj"

        # Make open() blow up to prove the fast path doesn't read the file
        original_open = open

        def forbidden_open(path, *args, **kwargs):
            if str(path).endswith(".jsonl"):
                raise AssertionError(f"fast path should not open JSONL: {path}")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", forbidden_open)
        # Must not raise
        result = mgr.resolve_session_path_for_window("@5")
        assert result == jsonl

    async def test_find_users_for_session_in_memory_only(
        self, mgr: SessionManager, monkeypatch
    ) -> None:
        # Set up two windows with different sessions, one user has both bound
        mgr.bind_thread(100, 1, "@1")
        mgr.bind_thread(100, 2, "@2")
        mgr.get_window_state("@1").session_id = "sess-a"
        mgr.get_window_state("@2").session_id = "sess-b"

        # Sentinel: the old impl called resolve_session_for_window which hits disk.
        # Fail loudly if anyone tries.
        async def forbidden(*args, **kwargs):
            raise AssertionError("find_users_for_session must not read JSONL")

        monkeypatch.setattr(mgr, "resolve_session_for_window", forbidden)

        result = await mgr.find_users_for_session("sess-a")
        assert result == [(100, "@1", 1)]

        result_b = await mgr.find_users_for_session("sess-b")
        assert result_b == [(100, "@2", 2)]

        result_none = await mgr.find_users_for_session("sess-missing")
        assert result_none == []

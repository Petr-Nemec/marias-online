import json

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from marias.server import protocol
from marias.server.app import create_app, origin_allowed
from marias.server.config import Settings

ORIGIN = {"origin": "http://testserver"}


@pytest.fixture
def client():
    with TestClient(create_app(Settings())) as test_client:
        yield test_client


def receive_until(ws, kind, limit=50):
    for _ in range(limit):
        message = ws.receive_json()
        if message["type"] == kind:
            return message
    raise AssertionError(f"no {kind!r} message")


def hello(ws, name="Petr", token=None):
    message = {"type": "hello", "name": name}
    if token:
        message["token"] = token
    ws.send_json(message)
    return receive_until(ws, "welcome")


# ------------------------------------------------------------------ protocol


def test_protocol_rejects_unknown_fields_and_wrong_types():
    parse = protocol.parse_client_message
    assert isinstance(parse('{"type":"ping"}'), protocol.Ping)
    for raw in (
        '{"type":"ping","x":1}',
        '{"type":"nope"}',
        '{"type":"action","action":{"a":"bid","level":true}}',
        '{"type":"action","action":{"a":"bid","level":"3"}}',
        '{"type":"action","action":{"a":"play","card":"zz"}}',
        '{"type":"action","action":{"a":"declare","discard":["h7","h8","h9"]}}',
        '{"type":"join_table","table":"abc"}',
        '{"type":"create_table","seats":5}',
        "[]",
        "not json",
    ):
        with pytest.raises(ValidationError):
            parse(raw)


def test_clean_text_strips_control_and_bidi_characters():
    assert protocol.clean_text("  Petr\u202e\u0000  Němec\n ", 20) == "Petr Němec"
    assert protocol.clean_text("x" * 50, 20) == "x" * 20


def test_origin_check():
    settings = Settings()
    assert origin_allowed({"origin": "https://marias.example", "host": "marias.example"}, settings)
    assert not origin_allowed({"origin": "https://evil.example", "host": "marias.example"}, settings)
    assert not origin_allowed({"origin": "null", "host": "marias.example"}, settings)
    assert origin_allowed({"host": "marias.example"}, settings)  # non-browser client
    pinned = Settings(allowed_origins=("https://marias.example",))
    assert origin_allowed({"origin": "https://marias.example", "host": "localhost"}, pinned)
    assert not origin_allowed({"origin": "https://other.example", "host": "localhost"}, pinned)


# ---------------------------------------------------------------------- HTTP


def test_health_and_security_headers(client):
    response = client.get("/healthz")
    assert response.status_code == 200 and response.json()["status"] == "ok"
    page = client.get("/")
    assert page.status_code == 200 and "Mariáš Online" in page.text
    headers = page.headers
    assert "default-src 'self'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in headers
    assert "server" not in headers or "uvicorn" not in headers["server"].lower()


def test_static_files_cannot_escape_the_web_root(client):
    for path in ("/../marias/table.py", "/%2e%2e/marias/table.py", "/js/../../table.py"):
        assert client.get(path).status_code == 404


def test_hsts_when_enabled():
    with TestClient(create_app(Settings(hsts=True))) as test_client:
        assert "max-age" in test_client.get("/").headers["strict-transport-security"]


# ----------------------------------------------------------------- WebSocket


def test_cross_site_websocket_is_refused(client):
    with (
        pytest.raises(WebSocketDisconnect) as error,
        client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws,
    ):
        ws.receive_text()
    assert error.value.code == 1008


def test_first_message_must_be_hello(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        ws.send_json({"type": "ready"})
        assert ws.receive_json()["code"] == "no_session"
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_full_game_against_bots(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        welcome = hello(ws)
        assert welcome["player"]["name"] == "Petr" and len(welcome["token"]) > 30
        receive_until(ws, "lobby")
        ws.send_json({"type": "create_table", "name": "U Petra", "stake": 20})
        state = receive_until(ws, "table")["state"]
        assert state["you"]["seat"] == 0 and state["options"]["name"] == "U Petra"
        ws.send_json({"type": "add_bot", "seat": 1})
        ws.send_json({"type": "add_bot", "seat": 2})
        ws.send_json({"type": "ready"})
        # Play by always choosing the first legal option until the deal is over.
        for _ in range(400):
            message = ws.receive_json()
            if message["type"] == "error":
                pytest.fail(message)
            if message["type"] != "table":
                continue
            state = message["state"]
            if state["status"] == "between":
                result = state["deal"]["result"]
                assert result is not None
                assert sum(s["money"] for s in state["seats"]) == 0
                break
            options = state["deal"] and state["deal"]["options"]
            if not options:
                continue
            if options["kind"] == "bid":
                ws.send_json({"type": "action", "action": {"a": "pass"}})
            elif options["kind"] == "talon":
                ws.send_json({"type": "action", "action": {"a": "omyl"}})
            elif options["kind"] == "flek":
                ws.send_json({"type": "action", "action": {"a": "flek", "parts": []}})
            elif options["kind"] == "play":
                ws.send_json({"type": "action", "action": {"a": "play", "card": options["cards"][0]}})
        else:
            pytest.fail("the deal did not finish")


def test_invalid_and_oversized_messages_are_answered_with_errors(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        hello(ws)
        ws.send_text("garbage")
        assert receive_until(ws, "error")["code"] == "bad_message"
        ws.send_text(json.dumps({"type": "chat", "text": "x" * 3000}))
        assert receive_until(ws, "error")["code"] == "too_large"
        ws.send_json({"type": "chat", "text": "ahoj"})
        assert receive_until(ws, "error")["code"] == "no_table"


def test_flooding_closes_the_connection(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        hello(ws)
        for _ in range(200):
            ws.send_text("garbage")
        with pytest.raises(WebSocketDisconnect) as error:  # noqa: PT012
            for _ in range(400):
                ws.receive_json()
        assert error.value.code == 1008


def test_reconnect_with_token_returns_to_the_seat(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        token = hello(ws)["token"]
        ws.send_json({"type": "create_table"})
        table_id = receive_until(ws, "table")["state"]["id"]
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        welcome = hello(ws, token=token)
        assert welcome["token"] == token
        state = receive_until(ws, "table")["state"]
        assert state["id"] == table_id and state["you"]["seat"] == 0


def test_second_window_replaces_the_first(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as first:
        token = hello(first)["token"]
        with client.websocket_connect("/ws", headers=ORIGIN) as second:
            hello(second, token=token)
            assert receive_until(first, "replaced")
            with pytest.raises(WebSocketDisconnect) as error:
                first.receive_json()
            assert error.value.code == 4001


def test_forged_token_gets_a_fresh_identity(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        welcome = hello(ws, token="A" * 43)
        assert welcome["token"] != "A" * 43


def test_private_table_needs_its_code(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as owner:
        hello(owner, "Majitel")
        owner.send_json({"type": "create_table", "private": True})
        state = receive_until(owner, "table")["state"]
        table_id, code = state["id"], state["code"]
        assert code
        with client.websocket_connect("/ws", headers=ORIGIN) as guest:
            hello(guest, "Host")
            lobby = receive_until(guest, "lobby")
            assert all(t["id"] != table_id for t in lobby["tables"])
            guest.send_json({"type": "join_table", "table": table_id})
            assert receive_until(guest, "error")["code"] == "no_such_table"
            wrong = "ZZZZZZ" if code != "ZZZZZZ" else "YYYYYY"
            guest.send_json({"type": "join_table", "table": table_id, "code": wrong})
            assert receive_until(guest, "error")["code"] == "no_such_table"
            guest.send_json({"type": "join_table", "table": table_id, "code": code})
            assert receive_until(guest, "table")["state"]["you"]["seat"] == 1


def test_names_are_sanitised(client):
    with client.websocket_connect("/ws", headers=ORIGIN) as ws:
        welcome = hello(ws, name="<b>\u202eX</b>")
        assert welcome["player"]["name"] == "<b>X</b>"  # stored as text, rendered as text
        ws.send_json({"type": "set_name", "name": "a"})
        assert receive_until(ws, "error")["code"] == "bad_name"


def test_guest_identities_are_capped(monkeypatch):
    from marias.server import hub as hub_module

    monkeypatch.setattr(hub_module, "MAX_SESSIONS", 5)
    app = create_app(Settings())
    with TestClient(app) as test_client:
        tokens = []
        for i in range(12):
            with test_client.websocket_connect("/ws", headers=ORIGIN) as ws:
                tokens.append(hello(ws, name=f"Host {i}")["token"])
        assert len(app.state.hub.sessions) <= 5
        # The most recent identity survives and is recognised again.
        with test_client.websocket_connect("/ws", headers=ORIGIN) as ws:
            assert hello(ws, token=tokens[-1])["token"] == tokens[-1]


def test_connection_counters_are_released():
    app = create_app(Settings(max_connections_per_ip=3))
    with TestClient(app) as test_client:
        for i in range(10):  # far more than the per-IP limit, one after another
            with test_client.websocket_connect("/ws", headers=ORIGIN) as ws:
                hello(ws, name=f"Host {i}")
        hub = app.state.hub
        assert hub.clients == set() and hub._per_ip == {}


def test_site_info_for_the_privacy_notice():
    settings = Settings(operator="Petr Němec", contact="info@example.cz", session_ttl=7200)
    with TestClient(create_app(settings)) as test_client:
        info = test_client.get("/api/info").json()
    assert info["operator"] == "Petr Němec" and info["contact"] == "info@example.cz"
    assert info["session_hours"] == 2


def test_two_missed_turns_send_the_player_back_to_the_lobby():
    from marias.table import KICK_REASON

    app = create_app(Settings())
    with TestClient(app) as test_client, test_client.websocket_connect("/ws", headers=ORIGIN) as ws:
        hello(ws)
        ws.send_json({"type": "create_table", "turn_seconds": 30})
        table_id = receive_until(ws, "table")["state"]["id"]
        table = app.state.hub.tables[table_id]
        ws.send_json({"type": "add_bot", "seat": 1})
        ws.send_json({"type": "add_bot", "seat": 2})
        ws.send_json({"type": "ready"})
        for _ in range(2000):
            message = ws.receive_json()
            if message["type"] == "left":
                assert message["reason"] == KICK_REASON
                break
            if message["type"] != "table":
                continue
            state = message["state"]
            if state["status"] == "between":
                ws.send_json({"type": "ready"})
            elif state["turn_seat"] == 0 and table.deadline:
                table.deadline = 0.0  # let the clock run out at once
        else:
            pytest.fail("the player was never removed")
        assert table.seat_of(next(iter(app.state.hub.sessions))) is None

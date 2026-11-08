from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.errors import LlmError
from app.main import create_app

TOKEN = "t" * 32
PASSWORD = "pw-for-tests"
HEADERS = {"X-Stand-In": "1"}


def test_requires_session(settings) -> None:
    anon = TestClient(create_app(settings))
    assert anon.get("/api/state").status_code == 401
    assert anon.post("/api/chat", json={"text": "hi"}, headers=HEADERS).status_code == 401


def test_root_without_cookie_explains_the_token(settings) -> None:
    anon = TestClient(create_app(settings))
    response = anon.get("/")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("text/html")
    assert "/c/" in response.text


def test_wrong_token_shows_html(settings) -> None:
    anon = TestClient(create_app(settings))
    response = anon.get("/c/" + "x" * 32, follow_redirects=False)
    assert response.status_code == 403
    assert "链接" in response.text


def test_localhost_auto_login(settings, workspace) -> None:
    dist = workspace / "web" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("<html>ok</html>", encoding="utf-8")
    local = TestClient(create_app(settings), client=("127.0.0.1", 50000))
    first = local.get("/", follow_redirects=False)
    assert first.status_code == 302
    assert local.get("/").status_code == 200


def test_proxied_localhost_still_needs_token(settings) -> None:
    proxied = TestClient(
        create_app(settings),
        client=("127.0.0.1", 50000),
        headers={"X-Forwarded-For": "203.0.113.9"},
    )
    assert proxied.get("/").status_code == 401


def test_wrong_token_is_forbidden(settings) -> None:
    client = TestClient(create_app(settings))
    assert client.get("/c/" + "x" * 32, follow_redirects=False).status_code == 403


def test_chat_returns_parts(client) -> None:
    response = client.post(
        "/api/chat", json={"text": "今天好累啊", "client_msg_id": "m1"}, headers=HEADERS
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "reply"
    assert 1 <= len(body["parts"]) <= 4
    assert all(part["delay_ms"] >= 0 for part in body["parts"])


def test_state_uses_owner_name_as_display_name(client) -> None:
    assert client.get("/api/state").json()["display_name"] == "阿哲"


def test_identity_question_uses_normal_reply_path(client) -> None:
    response = client.post(
        "/api/chat", json={"text": "你是不是AI", "client_msg_id": "identity"}, headers=HEADERS
    )
    assert response.status_code == 200
    assert response.json()["fixed"] is False


def test_record_answer_does_not_promise_unimplemented_self_service_delete(client) -> None:
    response = client.post(
        "/api/chat", json={"text": "是不是都记下来了", "client_msg_id": "record"}, headers=HEADERS
    )
    assert response.status_code == 200
    answer = " ".join(part["text"] for part in response.json()["parts"])
    assert "阿哲本人能看到" in answer
    assert "目前没有自助删除入口" in answer
    assert "我可以删" not in answer


def test_duplicate_client_msg_id_is_idempotent(client) -> None:
    first = client.post(
        "/api/chat", json={"text": "在吗", "client_msg_id": "dup-1"}, headers=HEADERS
    ).json()
    second = client.post(
        "/api/chat", json={"text": "在吗", "client_msg_id": "dup-1"}, headers=HEADERS
    ).json()
    assert [p["text"] for p in second["parts"]] == [p["text"] for p in first["parts"]]
    assert all(p["delay_ms"] == 0 for p in second["parts"])
    assert len(client.get("/api/messages").json()) == 2


def test_csrf_header_is_required(client) -> None:
    assert client.post("/api/chat", json={"text": "hi"}).status_code == 403


def test_guard_bypasses_model_and_notifies_owner(client) -> None:
    response = client.post("/api/chat", json={"text": "我不想活了"}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["fixed"] is True
    unread = client.app.state.ctx.inbox.unread()
    assert any(item["kind"] == "crisis" for item in unread)


def test_control_mutes_and_state_reflects_it(client) -> None:
    assert client.post("/api/control", json={"action": "mute"}, headers=HEADERS).status_code == 200
    assert client.get("/api/state").json()["muted"] is True


def test_llm_failure_returns_503(client) -> None:
    class Broken:
        def complete(self, *args, **kwargs):
            raise LlmError("boom")

    client.app.state.ctx.reply._llm = Broken()
    response = client.post("/api/chat", json={"text": "今天吃什么"}, headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == 503


def test_owner_login(client) -> None:
    wrong = client.post("/api/owner/login", json={"password": "nope"}, headers=HEADERS)
    assert wrong.status_code == 401
    ok = client.post("/api/owner/login", json={"password": PASSWORD}, headers=HEADERS)
    assert ok.status_code == 200
    assert client.get("/api/owner/session").status_code == 200

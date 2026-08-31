from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient


def register_user(client: TestClient, email: str, password: str) -> None:
    payload = {
        "email": email,
        "password": password,
        "full_name": "Usuario Test",
        "dob": str(date(1990, 1, 1)),
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_register_and_login(client: TestClient):
    email = "usuario1@example.com"
    password = "Password123!"
    register_user(client, email, password)
    token = login(client, email, password)
    assert token


def test_topup_approval_flow(client: TestClient):
    email = "usuario2@example.com"
    password = "Password123!"
    register_user(client, email, password)
    token = login(client, email, password)

    files = {"proof": ("comprobante.png", b"fake", "image/png")}
    data = {"amount": "150", "bank_name": "Banco Demo", "ref_number": "REF123"}
    response = client.post("/wallet/topups", data=data, files=files, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    topup_id = response.json()["id"]

    admin_token = login(client, "admin@example.com", "Admin1234!")
    review = client.patch(
        f"/wallet/topups/{topup_id}",
        json={"status": "APPROVED"},
        headers=auth_headers(admin_token),
    )
    assert review.status_code == 200

    balance = client.get("/wallet/balance/me", headers=auth_headers(token))
    assert balance.status_code == 200
    assert Decimal(balance.json()["balance"]) >= Decimal("150")


def test_bet_settlement_flow(client: TestClient):
    email = "apostador@example.com"
    password = "Password123!"
    register_user(client, email, password)
    token = login(client, email, password)

    files = {"proof": ("comprobante.png", b"fake2", "image/png")}
    data = {"amount": "200", "bank_name": "Banco Demo", "ref_number": "REFBET"}
    response = client.post("/wallet/topups", data=data, files=files, headers=auth_headers(token))
    assert response.status_code == 201
    topup_id = response.json()["id"]

    admin_token = login(client, "admin@example.com", "Admin1234!")
    client.patch(
        f"/wallet/topups/{topup_id}",
        json={"status": "APPROVED"},
        headers=auth_headers(admin_token),
    )

    tournaments = client.get("/tournaments")
    assert tournaments.status_code == 200
    tournament_id = tournaments.json()[0]["id"]

    matches_resp = client.get(f"/tournaments/{tournament_id}/matches")
    assert matches_resp.status_code == 200
    match = matches_resp.json()[0]

    markets_resp = client.get(f"/tournaments/matches/{match['id']}/markets")
    assert markets_resp.status_code == 200
    market = markets_resp.json()[0]

    bet_resp = client.post(
        "/bets",
        json={"market_id": market["id"], "selection": "HOME", "stake": "50"},
        headers=auth_headers(token),
    )
    assert bet_resp.status_code == 200
    bet_id = bet_resp.json()["id"]

    result_payload = {"home_score": 3, "away_score": 1, "state": "FINISHED"}
    close_resp = client.patch(
        f"/tournaments/matches/{match['id']}/result",
        json=result_payload,
        headers=auth_headers(admin_token),
    )
    assert close_resp.status_code == 200

    bets_resp = client.get("/bets/me", headers=auth_headers(token))
    assert bets_resp.status_code == 200
    bet = next(b for b in bets_resp.json() if b["id"] == bet_id)
    assert bet["status"] in {"WON", "LOST", "VOID"}

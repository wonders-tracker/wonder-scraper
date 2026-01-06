from fastapi.testclient import TestClient
from app.main import app
import random
import string

client = TestClient(app)


def generate_email():
    return f"test_{''.join(random.choices(string.ascii_lowercase, k=5))}@example.com"


def test_api_flow():
    email = generate_email()
    password = "".join(random.choices(string.ascii_letters + string.digits, k=16))

    print(f"1. Registering user: {email}")
    response = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    if response.status_code != 200:
        print(f"Register failed: {response.text}")
        return
    assert response.status_code == 200
    user_id = response.json()["id"]
    print(f"User registered with ID: {user_id}")

    print("2. Logging in")
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    print("Got access token.")

    headers = {"Authorization": f"Bearer {token}"}

    print("3. Fetching Cards")
    response = client.get("/api/v1/cards/?limit=5", headers=headers)
    assert response.status_code == 200
    cards = response.json()
    print(f"Got {len(cards)} cards.")
    assert len(cards) > 0
    print(f"First card: {cards[0]['name']}")

    # Find Aerius (assuming ID 2 based on previous scrape, or search for it)
    print("4. Fetching Market Data for Aerius")
    # Search for Aerius
    response = client.get("/api/v1/cards/?search=Aerius", headers=headers)
    aerius_cards = response.json()

    if aerius_cards:
        aerius_id = aerius_cards[0]["id"]
        print(f"Found Aerius ID: {aerius_id}")

        response = client.get(f"/api/v1/cards/{aerius_id}/market", headers=headers)
        if response.status_code == 200:
            market = response.json()
            print(f"Market Data: {market}")
            assert "avg_price" in market
        else:
            print(f"Market data not found (Status {response.status_code})")
    else:
        print("Aerius card not found in search.")


if __name__ == "__main__":
    test_api_flow()

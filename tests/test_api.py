import pytest
from httpx import ASGITransport, AsyncClient

from project.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_create_and_get_item(client: AsyncClient):
    payload = {"name": "Widget", "description": "A useful widget", "price": 9.99}

    # Create
    resp = await client.post("/api/items/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Widget"
    assert "id" in data

    # Read back
    item_id = data["id"]
    resp = await client.get(f"/api/items/{item_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Widget"


@pytest.mark.anyio
async def test_list_items(client: AsyncClient):
    resp = await client.get("/api/items/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_item_not_found(client: AsyncClient):
    resp = await client.get("/api/items/999999")
    assert resp.status_code == 404

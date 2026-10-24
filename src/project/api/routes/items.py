from fastapi import APIRouter, HTTPException

from project.models.item import ItemCreate, ItemRead

router = APIRouter()

# In-memory store (replace with a real DB later)
_items: dict[int, ItemRead] = {}
_next_id: int = 1


@router.get("/", response_model=list[ItemRead])
async def list_items() -> list[ItemRead]:
    """Return all items."""
    return list(_items.values())


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int) -> ItemRead:
    """Return a single item by ID."""
    item = _items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.post("/", response_model=ItemRead, status_code=201)
async def create_item(body: ItemCreate) -> ItemRead:
    """Create a new item."""
    global _next_id
    item = ItemRead(id=_next_id, **body.model_dump())
    _items[_next_id] = item
    _next_id += 1
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int) -> None:
    """Delete an item by ID."""
    if item_id not in _items:
        raise HTTPException(status_code=404, detail="Item not found")
    del _items[item_id]

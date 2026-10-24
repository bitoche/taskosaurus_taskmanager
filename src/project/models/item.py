from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    """Schema for creating an item."""

    name: str = Field(..., min_length=1, max_length=255, examples=["Widget"])
    description: str | None = Field(None, max_length=1000, examples=["A useful widget"])
    price: float = Field(..., gt=0, examples=[9.99])


class ItemRead(BaseModel):
    """Schema returned when reading an item."""

    id: int
    name: str
    description: str | None = None
    price: float

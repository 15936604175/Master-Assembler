from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Literal


class ItemInput(BaseModel):
    id: str = Field(min_length=1, description="Item SKU ID")
    length: float = Field(gt=0, description="Item length (mm)")
    width: float = Field(gt=0, description="Item width (mm)")
    height: float = Field(gt=0, description="Item height (mm)")
    weight: float = Field(gt=0, description="Item weight (kg)")
    quantity: int = Field(gt=0, le=10000, description="Item quantity")
    is_fragile: Optional[bool] = Field(default=False, description="Whether the item is fragile")
    batch_number: int = Field(default=0, ge=0, description="Batch number, smaller is placed first")
    forbidden_horizontal_dim: Optional[Literal["length", "width", "height"]] = Field(
        default=None,
        description="Which dimension cannot be horizontal: 'length', 'width', 'height', or null"
    )

    @field_validator("forbidden_horizontal_dim")
    @classmethod
    def validate_forbidden_dim(cls, v):
        if v is not None and v not in ("length", "width", "height"):
            raise ValueError("forbidden_horizontal_dim must be 'length', 'width', 'height' or null")
        return v


class ItemInstance(BaseModel):
    item_id: str
    length: float
    width: float
    height: float
    weight: float
    is_fragile: bool = False
    batch_number: int = 0
    forbidden_horizontal_dim: Optional[str] = None

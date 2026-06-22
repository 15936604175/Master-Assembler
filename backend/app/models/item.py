from pydantic import BaseModel, Field, field_validator
from typing import List


class ItemInput(BaseModel):
    id: str = Field(min_length=1, description="Item SKU ID")
    length: float = Field(gt=0, description="Item length (mm)")
    width: float = Field(gt=0, description="Item width (mm)")
    height: float = Field(gt=0, description="Item height (mm)")
    weight: float = Field(gt=0, description="Item weight (kg)")
    quantity: int = Field(gt=0, le=10000, description="Item quantity")
    is_fragile: bool = Field(default=False, description="Whether the item is fragile")
    batch_number: int = Field(default=0, ge=0, description="Batch number, smaller is placed first")
    forbidden_horizontal_dims: List[str] = Field(
        default_factory=list,
        description="禁止与地面垂直的维度（即禁止该维度朝上）。最多 2 个参数。"
                    "Values: 'length', 'width', 'height'. "
                    "e.g. ['height'] = height 不能朝上（排除 height_vertical）；"
                    "['height', 'width'] = 只允许 length_vertical。"
    )

    @field_validator("forbidden_horizontal_dims")
    @classmethod
    def validate_forbidden_dims(cls, v):
        allowed = {"length", "width", "height"}
        if not all(dim in allowed for dim in v):
            raise ValueError(
                f"forbidden_horizontal_dims must contain only 'length', 'width', 'height'"
            )
        if len(v) > 2:
            raise ValueError(
                f"forbidden_horizontal_dims 最多 2 个参数（至少要有一个维度可以垂直），实际: {v}"
            )
        return v


class ItemInstance(BaseModel):
    item_id: str
    length: float
    width: float
    height: float
    weight: float
    is_fragile: bool = False
    batch_number: int = 0
    forbidden_horizontal_dims: List[str] = Field(default_factory=list)

from pydantic import BaseModel, Field


class ContainerConfig(BaseModel):
    length: float = Field(gt=0, description="Container inner length (mm)")
    width: float = Field(gt=0, description="Container inner width (mm)")
    height: float = Field(gt=0, description="Container inner height (mm)")
    max_weight: float = Field(gt=0, description="Maximum load weight (kg)")

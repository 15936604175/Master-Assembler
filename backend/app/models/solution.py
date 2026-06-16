from pydantic import BaseModel, Field
from typing import List, Optional
from app.models.container import ContainerConfig
from app.models.item import ItemInput


class Placement(BaseModel):
    item_id: str
    x: float
    y: float
    z: float
    length: float
    width: float
    height: float
    rotation: str
    orientation: Optional[str] = None
    is_fragile: Optional[bool] = False


class UnplacedItem(BaseModel):
    item_id: str
    quantity: int
    reason: str


class CGPoint(BaseModel):
    x: float
    y: float
    z: float


class Stats(BaseModel):
    total_items_placed: int
    total_items_unplaced: int
    algorithm_time_ms: float


class SolutionMetrics(BaseModel):
    avg_support_ratio: float = 1.0
    cg_offset_x: float = 0.0
    cg_offset_z: float = 0.0
    fragile_violations: int = 0


class OptimizeRequest(BaseModel):
    container: ContainerConfig
    items: List[ItemInput]


class OptimizeResponse(BaseModel):
    success: bool
    container_utilization: float
    weight_utilization: float
    total_weight: float
    placements: List[Placement]
    unplaced_items: List[UnplacedItem]
    center_of_gravity: CGPoint
    stats: Stats
    metrics: Optional[SolutionMetrics] = None
    cg_deviation_ratio: Optional[float] = None
    solution_type: Optional[str] = None
    feasibility_report: Optional[dict] = None


class MultiOptimizeResponse(BaseModel):
    success: bool
    primary: OptimizeResponse
    pareto_solutions: Optional[List[OptimizeResponse]] = None
    ga_solution: Optional[OptimizeResponse] = None
    ls_solution: Optional[OptimizeResponse] = None
    algorithm_time_ms: float
    pareto_count: int = 0

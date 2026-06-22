from fastapi import APIRouter, HTTPException
from typing import List, Dict
from collections import Counter
import time
import logging
from app.models.solution import (
    OptimizeRequest, OptimizeResponse,
    Placement, UnplacedItem, CGPoint, Stats, SolutionMetrics
)
from app.validators.item_validator import validate_request
from app.engine.feasibility import FeasibilityVerifier

router = APIRouter()
logger = logging.getLogger(__name__)


def _compute_unplaced(items, placements_dicts) -> List[UnplacedItem]:
    """Compute unplaced items by comparing requested quantities with placed counts."""
    placed_counter: Counter = Counter(p["item_id"] for p in placements_dicts)
    unplaced: List[UnplacedItem] = []
    for item in items:
        total_qty = item.quantity
        placed_qty = placed_counter.get(item.id, 0)
        unplaced_qty = total_qty - placed_qty
        if unplaced_qty > 0:
            unplaced.append(UnplacedItem(
                item_id=item.id,
                quantity=unplaced_qty,
                reason="空间不足或无法满足支撑条件",
            ))
    return unplaced


def _build_response_from_dicts(container, items,
                                placements_dicts: List[Dict],
                                solution_type: str, stats_time_ms: int = 0):
    """Build OptimizeResponse directly from raw placement dictionaries."""
    if not placements_dicts:
        return None

    container_vol = container.length * container.height * container.width
    placed_vol = sum(p["l"] * p["h"] * p["w"] for p in placements_dicts)
    placed_weight = sum(p.get("weight", 0) for p in placements_dicts)

    verifier = FeasibilityVerifier(container, items)
    report = verifier.verify(placements_dicts)

    total_w = sum(p.get("weight", 0) for p in placements_dicts)
    if total_w > 0:
        cg_x = sum(p.get("weight", 0) * (p["x"] + p["l"] / 2) for p in placements_dicts) / total_w
        cg_y = sum(p.get("weight", 0) * (p["y"] + p["h"] / 2) for p in placements_dicts) / total_w
        cg_z = sum(p.get("weight", 0) * (p["z"] + p["w"] / 2) for p in placements_dicts) / total_w
    else:
        total_vol = sum(p["l"] * p["h"] * p["w"] for p in placements_dicts)
        if total_vol > 0:
            cg_x = sum((p["x"] + p["l"] / 2) * p["l"] * p["h"] * p["w"] for p in placements_dicts) / total_vol
            cg_y = sum((p["y"] + p["h"] / 2) * p["l"] * p["h"] * p["w"] for p in placements_dicts) / total_vol
            cg_z = sum((p["z"] + p["w"] / 2) * p["l"] * p["h"] * p["w"] for p in placements_dicts) / total_vol
        else:
            cg_x = cg_y = cg_z = 0.0

    utilization = round(placed_vol / container_vol, 4) if container_vol > 0 else 0
    weight_utilization = round(placed_weight / container.max_weight, 4) if container.max_weight > 0 else 0

    unplaced_items = _compute_unplaced(items, placements_dicts)
    total_unplaced = sum(u.quantity for u in unplaced_items)

    metrics = SolutionMetrics(
        avg_support_ratio=round(report.support_score, 4),
        cg_offset_x=round(abs(cg_x - container.length / 2), 2),
        cg_offset_z=round(abs(cg_z - container.width / 2), 2),
        fragile_violations=report.fragile_violations,
    )

    response = OptimizeResponse(
        success=True,
        container_utilization=utilization,
        weight_utilization=weight_utilization,
        total_weight=round(placed_weight, 2),
        placements=[
            Placement(
                item_id=p["item_id"], x=round(p["x"], 2), y=round(p["y"], 2),
                z=round(p["z"], 2), length=round(p["l"], 2), width=round(p["w"], 2),
                height=round(p["h"], 2), rotation=p.get("rotation", "lwh"),
                orientation=p.get("orientation"), is_fragile=p.get("is_fragile", False),
                weight=p.get("weight", 0.0),
            )
            for p in placements_dicts
        ],
        unplaced_items=unplaced_items,
        center_of_gravity=CGPoint(x=round(cg_x, 2), y=round(cg_y, 2), z=round(cg_z, 2)),
        stats=Stats(
            total_items_placed=len(placements_dicts),
            total_items_unplaced=total_unplaced,
            algorithm_time_ms=stats_time_ms,
        ),
        metrics=metrics,
        solution_type=solution_type,
        cg_deviation_ratio=report.cg_deviation_ratio,
        feasibility_report={
            "is_feasible": report.is_feasible,
            "geometry_ok": report.geometry_ok,
            "physics_ok": report.physics_ok,
            "orientation_ok": report.orientation_ok,
            "stability_score": report.stability_score,
            "support_score": report.support_score,
            "fragile_violations": report.fragile_violations,
            "orientation_violations": report.orientation_violations,
            "messages": report.messages,
        },
    )
    return response


@router.post("/optimize-block", response_model=OptimizeResponse)
async def optimize_block(request: OptimizeRequest):
    """Block 块状优化接口（V1 基础版）。"""
    try:
        is_valid, errors = validate_request(request.container, request.items)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "输入数据验证失败", "errors": errors},
            )
        from app.engine.block_optimizer import BlockOptimizer
        start = time.time()
        block_packer = BlockOptimizer()
        placements = block_packer.pack(request.container, request.items)
        elapsed = (time.time() - start) * 1000
        response = _build_response_from_dicts(
            request.container, request.items, placements, "block", round(elapsed, 2)
        )
        if response is None:
            raise HTTPException(status_code=500, detail="Block 优化未生成有效方案")
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize-advanced-block", response_model=OptimizeResponse)
async def optimize_advanced_block(request: OptimizeRequest):
    """高级 Block 块状优化接口（V2：Batch Corridor + Sequence Penalty + Beam Search）。"""
    try:
        is_valid, errors = validate_request(request.container, request.items)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "输入数据验证失败", "errors": errors},
            )
        from app.engine.advanced_block_optimizer import AdvancedBlockOptimizer
        start = time.time()
        advanced_packer = AdvancedBlockOptimizer()
        placements = advanced_packer.pack(request.container, request.items)
        elapsed = (time.time() - start) * 1000
        response = _build_response_from_dicts(
            request.container, request.items, placements, "advanced_block", round(elapsed, 2)
        )
        if response is None:
            raise HTTPException(status_code=500, detail="高级 Block 优化未生成有效方案")
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
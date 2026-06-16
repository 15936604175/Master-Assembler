from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict
from app.models.solution import OptimizeRequest, OptimizeResponse, MultiOptimizeResponse, Placement, UnplacedItem, CGPoint, Stats
from app.models.container import ContainerConfig
from app.engine.packer import EPacker
from app.validators.item_validator import validate_request
from app.engine.feasibility import FeasibilityVerifier

router = APIRouter()


def _build_response(result, solution_type: str, container: ContainerConfig,
                    items, time_ms: float) -> OptimizeResponse:
    """Build OptimizeResponse with feasibility report (from EPacker result)."""
    verifier = FeasibilityVerifier(container, items)
    placements_dicts = [
        {
            "item_id": p.item_id,
            "x": p.x, "y": p.y, "z": p.z,
            "l": p.length, "h": p.height, "w": p.width,
            "weight": 0.0,
            "is_fragile": p.is_fragile or False,
            "orientation": p.orientation,
        }
        for p in result.placements
    ]
    report = verifier.verify(placements_dicts)
    result.cg_deviation_ratio = report.cg_deviation_ratio
    result.solution_type = solution_type
    result.feasibility_report = {
        "is_feasible": report.is_feasible,
        "geometry_ok": report.geometry_ok,
        "physics_ok": report.physics_ok,
        "orientation_ok": report.orientation_ok,
        "stability_score": report.stability_score,
        "support_score": report.support_score,
        "fragile_violations": report.fragile_violations,
        "orientation_violations": report.orientation_violations,
        "messages": report.messages,
    }
    return result


def _build_response_from_dicts(container: ContainerConfig, items,
                                placements_dicts: List[Dict],
                                solution_type: str, stats_time_ms: int = 0) -> Optional[OptimizeResponse]:
    """Build OptimizeResponse directly from raw placement dictionaries."""
    if not placements_dicts:
        return None

    container_vol = container.length * container.height * container.width
    placed_vol = sum(p["l"] * p["h"] * p["w"] for p in placements_dicts)
    placed_weight = sum(p.get("weight", 0) for p in placements_dicts)

    verifier = FeasibilityVerifier(container, items)
    report = verifier.verify(placements_dicts)

    # Approximate center of gravity: average of placement centers weighted by volume
    cg_x, cg_y, cg_z = 0.0, 0.0, 0.0
    total_vol = 0.0
    for p in placements_dicts:
        vol = p["l"] * p["h"] * p["w"]
        cg_x += (p["x"] + p["l"] / 2) * vol
        cg_y += (p["y"] + p["h"] / 2) * vol
        cg_z += (p["z"] + p["w"] / 2) * vol
        total_vol += vol
    if total_vol > 0:
        cg_x /= total_vol
        cg_y /= total_vol
        cg_z /= total_vol

    utilization = round(placed_vol / container_vol, 4) if container_vol > 0 else 0
    weight_utilization = round(placed_weight / container.max_weight, 4) if container.max_weight > 0 else 0

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
            )
            for p in placements_dicts
        ],
        unplaced_items=[],
        center_of_gravity=CGPoint(x=round(cg_x, 2), y=round(cg_y, 2), z=round(cg_z, 2)),
        stats=Stats(
            total_items_placed=len(placements_dicts),
            total_items_unplaced=0,
            algorithm_time_ms=stats_time_ms,
        ),
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


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(request: OptimizeRequest):
    try:
        is_valid, errors = validate_request(request.container, request.items)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "输入数据验证失败",
                    "errors": errors,
                },
            )
        packer = EPacker()
        import time
        start = time.time()
        result = packer.pack(request.container, request.items)
        elapsed = (time.time() - start) * 1000
        result.stats.algorithm_time_ms = round(elapsed, 2)
        return _build_response(result, "greedy", request.container, request.items, elapsed)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize-phase2", response_model=MultiOptimizeResponse)
async def optimize_phase2(
    request: OptimizeRequest,
    enable_ga: bool = Query(True, description="启用遗传算法优化"),
    enable_ls: bool = Query(True, description="启用局部搜索优化"),
    enable_pareto: bool = Query(True, description="启用帕累托优化"),
):
    """
    Phase 2 多算法优化接口。

    同时运行贪心、遗传算法、局部搜索和帕累托优化，返回多个方案供选择。
    """
    try:
        is_valid, errors = validate_request(request.container, request.items)
        if not is_valid:
            raise HTTPException(
                status_code=422,
                detail={"message": "输入数据验证失败", "errors": errors},
            )

        import time
        total_start = time.time()

        # 1. Greedy (baseline)
        packer = EPacker()
        greedy_result = packer.pack(request.container, request.items)
        greedy_response = _build_response(
            greedy_result, "greedy", request.container, request.items, 0
        )

        # 2. Genetic Algorithm
        ga_response = None
        if enable_ga:
            from app.engine.genetic_algorithm import GeneticOptimizer, GAConfig
            ga = GeneticOptimizer(request.container, request.items, GAConfig(
                population_size=60, generations=80, elite_count=5
            ))
            ga_placements, _, _ = ga.run()
            if ga_placements:
                ga_response = _build_response_from_dicts(
                    request.container, request.items, ga_placements, "ga", 0
                )

        # 3. Local Search
        ls_response = None
        if enable_ls:
            from app.engine.local_search import LocalSearchOptimizer, LSConfig

            seed = ga.best_chromosome if (enable_ga and hasattr(ga, 'best_chromosome') and ga.best_chromosome) else None

            ls = LocalSearchOptimizer(request.container, request.items, seed, LSConfig(
                max_iterations=500, no_improve_limit=30, strategy="best"
            ))
            ls_result = ls.run()

            if ls_result.placements:
                ls_response = _build_response_from_dicts(
                    request.container, request.items, ls_result.placements,
                    "ls", ls_result.iterations_run
                )

        # 4. Pareto (NSGA-II)
        pareto_responses: list = []
        pareto_count = 0
        if enable_pareto:
            from app.engine.pareto_optimizer import NSGAOptimizer, NSGAConfig
            nsga = NSGAOptimizer(request.container, request.items, NSGAConfig(
                population_size=50, generations=60, elite_count=8
            ))
            pareto_result = nsga.run()
            pareto_count = len(pareto_result.pareto_front)

            for ind in pareto_result.pareto_front[:8]:
                if not ind.placements:
                    continue
                resp = _build_response_from_dicts(
                    request.container, request.items, ind.placements, "pareto", 0
                )
                if resp:
                    pareto_responses.append(resp)

        total_elapsed = (time.time() - total_start) * 1000

        return MultiOptimizeResponse(
            success=True,
            primary=greedy_response,
            ga_solution=ga_response,
            ls_solution=ls_response,
            pareto_solutions=pareto_responses if pareto_responses else None,
            algorithm_time_ms=round(total_elapsed, 2),
            pareto_count=pareto_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

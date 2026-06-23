/// API 路由模块

use axum::{
    Json, Router,
    http::StatusCode,
    routing::{get, post},
};
use tower_http::cors::{Any, CorsLayer};
use std::collections::HashMap;
use serde_json::json;

use crate::models::*;
use crate::validator::validate_request;
use crate::feasibility::FeasibilityVerifier;
use crate::block_optimizer::BlockOptimizer;
use crate::advanced_block_optimizer::AdvancedBlockOptimizer;

pub fn create_router() -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        .route("/health", get(health))
        .route("/api/optimize-block", post(optimize_block))
        .route("/api/optimize-advanced-block", post(optimize_advanced_block))
        .layer(cors)
}

async fn health() -> Json<serde_json::Value> {
    Json(json!({"status": "ok", "version": "1.0.0"}))
}

fn compute_unplaced(items: &[ItemInput], placements: &[PlacementInfo]) -> Vec<UnplacedItem> {
    let mut placed_counter: HashMap<String, i32> = HashMap::new();
    for p in placements {
        *placed_counter.entry(p.item_id.clone()).or_insert(0) += 1;
    }
    let mut unplaced = Vec::new();
    for item in items {
        let placed_qty = placed_counter.get(&item.id).copied().unwrap_or(0);
        let unplaced_qty = item.quantity - placed_qty;
        if unplaced_qty > 0 {
            unplaced.push(UnplacedItem {
                item_id: item.id.clone(),
                quantity: unplaced_qty,
                reason: "空间不足或无法满足支撑条件".to_string(),
            });
        }
    }
    unplaced
}

fn build_response(
    container: &ContainerConfig, items: &[ItemInput],
    placements: &[PlacementInfo], solution_type: &str, stats_time_ms: f64,
) -> Option<OptimizeResponse> {
    if placements.is_empty() { return None; }

    let container_vol = container.length * container.height * container.width;
    let placed_vol: f64 = placements.iter().map(|p| p.l * p.h * p.w).sum();
    let placed_weight: f64 = placements.iter().map(|p| p.weight).sum();

    let verifier = FeasibilityVerifier::new(container, items);
    let report = verifier.verify(placements);

    let total_w = placed_weight;
    let (cg_x, cg_y, cg_z) = if total_w > 0.0 {
        (
            placements.iter().map(|p| p.weight * (p.x + p.l / 2.0)).sum::<f64>() / total_w,
            placements.iter().map(|p| p.weight * (p.y + p.h / 2.0)).sum::<f64>() / total_w,
            placements.iter().map(|p| p.weight * (p.z + p.w / 2.0)).sum::<f64>() / total_w,
        )
    } else {
        let total_vol = placed_vol;
        if total_vol > 0.0 {
            (
                placements.iter().map(|p| (p.x + p.l / 2.0) * p.l * p.h * p.w).sum::<f64>() / total_vol,
                placements.iter().map(|p| (p.y + p.h / 2.0) * p.l * p.h * p.w).sum::<f64>() / total_vol,
                placements.iter().map(|p| (p.z + p.w / 2.0) * p.l * p.h * p.w).sum::<f64>() / total_vol,
            )
        } else { (0.0, 0.0, 0.0) }
    };

    let utilization = round_to(if container_vol > 0.0 { placed_vol / container_vol } else { 0.0 }, 4);
    let weight_utilization = round_to(if container.max_weight > 0.0 { placed_weight / container.max_weight } else { 0.0 }, 4);

    let unplaced_items = compute_unplaced(items, placements);
    let total_unplaced: i32 = unplaced_items.iter().map(|u| u.quantity).sum();

    let metrics = SolutionMetrics {
        avg_support_ratio: round_to(report.support_score, 4),
        cg_offset_x: round_to((cg_x - container.length / 2.0).abs(), 2),
        cg_offset_z: round_to((cg_z - container.width / 2.0).abs(), 2),
        fragile_violations: report.fragile_violations,
    };

    let feasibility_report = json!({
        "is_feasible": report.is_feasible,
        "geometry_ok": report.geometry_ok,
        "physics_ok": report.physics_ok,
        "orientation_ok": report.orientation_ok,
        "stability_score": report.stability_score,
        "support_score": report.support_score,
        "fragile_violations": report.fragile_violations,
        "orientation_violations": report.orientation_violations,
        "messages": report.messages,
    });

    Some(OptimizeResponse {
        success: true,
        container_utilization: utilization,
        weight_utilization,
        total_weight: round_to(placed_weight, 2),
        placements: placements.iter().map(|p| Placement {
            item_id: p.item_id.clone(),
            x: round_to(p.x, 2), y: round_to(p.y, 2), z: round_to(p.z, 2),
            length: round_to(p.l, 2), width: round_to(p.w, 2), height: round_to(p.h, 2),
            rotation: p.rotation.clone(),
            orientation: p.orientation.clone(),
            is_fragile: Some(p.is_fragile),
            weight: Some(p.weight),
        }).collect(),
        unplaced_items,
        center_of_gravity: CGPoint {
            x: round_to(cg_x, 2), y: round_to(cg_y, 2), z: round_to(cg_z, 2),
        },
        stats: Stats {
            total_items_placed: placements.len(),
            total_items_unplaced: total_unplaced,
            algorithm_time_ms: round_to(stats_time_ms, 2),
        },
        metrics: Some(metrics),
        solution_type: Some(solution_type.to_string()),
        cg_deviation_ratio: Some(report.cg_deviation_ratio),
        feasibility_report: Some(feasibility_report),
    })
}

async fn optimize_block(
    Json(request): Json<OptimizeRequest>,
) -> Result<Json<OptimizeResponse>, (StatusCode, Json<serde_json::Value>)> {
    let (is_valid, errors) = validate_request(&request.container, &request.items);
    if !is_valid {
        return Err((
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(json!({"message": "输入数据验证失败", "errors": errors})),
        ));
    }

    let start = std::time::Instant::now();
    let optimizer = BlockOptimizer::new();
    let placements = optimizer.pack(&request.container, &request.items);
    let elapsed = start.elapsed().as_secs_f64() * 1000.0;

    match build_response(&request.container, &request.items, &placements, "block", elapsed) {
        Some(response) => Ok(Json(response)),
        None => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"detail": "Block 优化未生成有效方案"})),
        )),
    }
}

async fn optimize_advanced_block(
    Json(request): Json<OptimizeRequest>,
) -> Result<Json<OptimizeResponse>, (StatusCode, Json<serde_json::Value>)> {
    let (is_valid, errors) = validate_request(&request.container, &request.items);
    if !is_valid {
        return Err((
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(json!({"message": "输入数据验证失败", "errors": errors})),
        ));
    }

    let start = std::time::Instant::now();
    let optimizer = AdvancedBlockOptimizer::new();
    let placements = optimizer.pack(&request.container, &request.items);
    let elapsed = start.elapsed().as_secs_f64() * 1000.0;

    match build_response(&request.container, &request.items, &placements, "advanced_block", elapsed) {
        Some(response) => Ok(Json(response)),
        None => Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({"detail": "高级 Block 优化未生成有效方案"})),
        )),
    }
}

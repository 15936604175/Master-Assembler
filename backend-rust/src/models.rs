use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// ─────────────────────────────────────────────────────────────
// API 模型 (与 Python FastAPI 版本完全一致)
// ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContainerConfig {
    pub length: f64,
    pub width: f64,
    pub height: f64,
    pub max_weight: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ItemInput {
    pub id: String,
    pub length: f64,
    pub width: f64,
    pub height: f64,
    pub weight: f64,
    pub quantity: i32,
    #[serde(default)]
    pub is_fragile: bool,
    #[serde(default)]
    pub batch_number: i32,
    #[serde(default)]
    pub forbidden_horizontal_dims: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizeRequest {
    pub container: ContainerConfig,
    pub items: Vec<ItemInput>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlacementInfo {
    pub item_id: String,
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub l: f64,
    pub h: f64,
    pub w: f64,
    #[serde(default)]
    pub weight: f64,
    #[serde(default)]
    pub is_fragile: bool,
    #[serde(default = "default_rotation")]
    pub rotation: String,
    pub orientation: Option<String>,
}

fn default_rotation() -> String {
    "lwh".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlockInfo {
    pub sku: String,
    pub batch: i32,
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub l: f64,
    pub h: f64,
    pub w: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Placement {
    pub item_id: String,
    pub x: f64,
    pub y: f64,
    pub z: f64,
    pub length: f64,
    pub width: f64,
    pub height: f64,
    pub rotation: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub orientation: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_fragile: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub weight: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnplacedItem {
    pub item_id: String,
    pub quantity: i32,
    pub reason: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CGPoint {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Stats {
    pub total_items_placed: usize,
    pub total_items_unplaced: i32,
    pub algorithm_time_ms: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SolutionMetrics {
    pub avg_support_ratio: f64,
    pub cg_offset_x: f64,
    pub cg_offset_z: f64,
    pub fragile_violations: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeasibilityReport {
    pub is_feasible: bool,
    pub geometry_ok: bool,
    pub physics_ok: bool,
    pub orientation_ok: bool,
    pub stability_score: f64,
    pub support_score: f64,
    pub fragile_violations: i32,
    pub orientation_violations: i32,
    pub messages: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizeResponse {
    pub success: bool,
    pub container_utilization: f64,
    pub weight_utilization: f64,
    pub total_weight: f64,
    pub placements: Vec<Placement>,
    pub unplaced_items: Vec<UnplacedItem>,
    pub center_of_gravity: CGPoint,
    pub stats: Stats,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metrics: Option<SolutionMetrics>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cg_deviation_ratio: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub solution_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub feasibility_report: Option<serde_json::Value>,
}

// ─────────────────────────────────────────────────────────────
// 引擎内部数据结构
// ─────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Block {
    pub sku: String,
    pub batch: i32,
    pub nx: usize,
    pub ny: usize,
    pub nz: usize,
    pub length: f64,
    pub height: f64,
    pub width: f64,
    pub volume: f64,
    pub count: usize,
    pub item_length: f64,
    pub item_height: f64,
    pub item_width: f64,
    pub item_weight: f64,
    pub is_fragile: bool,
    pub rotation_label: String,
    pub orientation_name: String,
    pub quality_score: f64,
}

#[derive(Debug, Clone)]
pub struct BeamState {
    pub placements: Vec<PlacementInfo>,
    pub placed_blocks: Vec<BlockInfo>,
    pub extreme_points: Vec<(f64, f64, f64)>,
    pub inventory: HashMap<String, i32>,
    pub score: f64,
    pub placed_volume: f64,
    pub placed_weight: f64,
    pub cg_x: f64,
    pub cg_y: f64,
    pub cg_z: f64,
    pub total_weight: f64,
}

#[derive(Debug, Clone)]
pub struct BatchCorridor {
    pub batch_id: i32,
    pub preferred_min_x: f64,
    pub preferred_max_x: f64,
    pub target_center_x: f64,
    pub total_volume: f64,
}

#[derive(Debug, Clone)]
pub struct AdvancedBeamState {
    pub placements: Vec<PlacementInfo>,
    pub placed_blocks: Vec<BlockInfo>,
    pub extreme_points: Vec<(f64, f64, f64)>,
    pub inventory: HashMap<String, i32>,
    pub score: f64,
    pub placed_volume: f64,
    pub placed_weight: f64,
    pub batch_min_x: HashMap<i32, f64>,
    pub batch_max_x: HashMap<i32, f64>,
    pub batch_volume: HashMap<i32, f64>,
}

#[derive(Debug, Clone)]
pub struct VerificationReport {
    pub is_feasible: bool,
    pub geometry_ok: bool,
    pub physics_ok: bool,
    pub orientation_ok: bool,
    pub stability_score: f64,
    pub support_score: f64,
    pub cg_deviation_ratio: f64,
    pub fragile_violations: i32,
    pub orientation_violations: i32,
    pub messages: Vec<String>,
}

// ─────────────────────────────────────────────────────────────
// 工具函数
// ─────────────────────────────────────────────────────────────

pub fn round_to(value: f64, places: u32) -> f64 {
    let factor = 10_f64.powi(places as i32);
    (value * factor).round() / factor
}

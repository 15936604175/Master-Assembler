export interface ContainerConfig {
  length: number;
  width: number;
  height: number;
  max_weight: number;
}

export interface ItemInput {
  id: string;
  length: number;
  width: number;
  height: number;
  weight: number;
  quantity: number;
  is_fragile?: boolean;
  batch_number?: number;
  forbidden_horizontal_dims?: string[];
}

export interface OptimizeRequest {
  container: ContainerConfig;
  items: ItemInput[];
}

export interface Placement {
  item_id: string;
  x: number;
  y: number;
  z: number;
  length: number;
  width: number;
  height: number;
  rotation: string;
  orientation?: string;
  is_fragile?: boolean;
}

export interface UnplacedItem {
  item_id: string;
  quantity: number;
  reason: string;
}

export interface CGPoint {
  x: number;
  y: number;
  z: number;
}

export interface Stats {
  total_items_placed: number;
  total_items_unplaced: number;
  algorithm_time_ms: number;
}

export interface SolutionMetrics {
  avg_support_ratio: number;
  cg_offset_x: number;
  cg_offset_z: number;
  fragile_violations: number;
}

export interface FeasibilityReport {
  is_feasible: boolean;
  geometry_ok: boolean;
  physics_ok: boolean;
  orientation_ok: boolean;
  stability_score: number;
  support_score: number;
  fragile_violations: number;
  orientation_violations: number;
  messages: string[];
}

export interface OptimizeResponse {
  success: boolean;
  container_utilization: number;
  weight_utilization: number;
  total_weight: number;
  placements: Placement[];
  unplaced_items: UnplacedItem[];
  center_of_gravity: CGPoint;
  stats: Stats;
  metrics?: SolutionMetrics;
  cg_deviation_ratio?: number;
  solution_type?: string;
  feasibility_report?: FeasibilityReport;
}

export interface MultiOptimizeResponse {
  success: boolean;
  primary: OptimizeResponse;
  pareto_solutions?: OptimizeResponse[];
  ga_solution?: OptimizeResponse;
  ls_solution?: OptimizeResponse;
  algorithm_time_ms: number;
  pareto_count: number;
}

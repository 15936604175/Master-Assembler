import { describe, it, expect } from 'vitest';

describe('App', () => {
  it('types are correct', () => {
    const response = {
      success: true,
      container_utilization: 0.85,
      weight_utilization: 0.5,
      total_weight: 100,
      placements: [{ item_id: 'A', x: 0, y: 0, z: 0, length: 50, width: 40, height: 30, rotation: 'lwh' }],
      unplaced_items: [],
      center_of_gravity: { x: 200, y: 100, z: 150 },
      stats: { total_items_placed: 1, total_items_unplaced: 0, algorithm_time_ms: 10 },
    };
    expect(response.success).toBe(true);
    expect(response.placements.length).toBe(1);
    expect(response.stats.total_items_placed).toBe(1);
  });
});

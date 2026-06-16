import type { OptimizeRequest, OptimizeResponse, MultiOptimizeResponse } from '../types';

const API_BASE = '/api';

export async function optimize(request: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error (${response.status}): ${text}`);
  }
  return response.json();
}

export async function optimizePhase2(
  request: OptimizeRequest,
  options?: {
    enable_ga?: boolean;
    enable_ls?: boolean;
    enable_pareto?: boolean;
  }
): Promise<MultiOptimizeResponse> {
  const params = new URLSearchParams();
  if (options?.enable_ga !== undefined) params.set('enable_ga', String(options.enable_ga));
  if (options?.enable_ls !== undefined) params.set('enable_ls', String(options.enable_ls));
  if (options?.enable_pareto !== undefined) params.set('enable_pareto', String(options.enable_pareto));

  const url = `${API_BASE}/optimize-phase2${params.toString() ? '?' + params.toString() : ''}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API error (${response.status}): ${text}`);
  }
  return response.json();
}

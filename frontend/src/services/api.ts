import type { OptimizeRequest, OptimizeResponse } from '../types';

const API_BASE = '/api';

export async function optimizeBlock(request: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/optimize-block`, {
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

export async function optimizeAdvancedBlock(request: OptimizeRequest): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/optimize-advanced-block`, {
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

import type { OptimizeRequest, OptimizeResponse } from '../types';
import { invoke } from '@tauri-apps/api/core';

// Cache the backend URL after first successful resolution
let cachedBaseUrl: string | null = null;

async function getApiBase(): Promise<string> {
  if (cachedBaseUrl) return cachedBaseUrl;

  // Dev mode: use Vite proxy
  if (import.meta.env.DEV) {
    cachedBaseUrl = '/api';
    return cachedBaseUrl;
  }

  // Production: ask Tauri for the actual backend URL (with retries)
  const maxRetries = 10;
  for (let i = 0; i < maxRetries; i++) {
    try {
      const backendUrl = await invoke<string>('get_backend_url');
      // Port 0 means backend hasn't bound yet, retry
      if (backendUrl.includes(':0')) {
        await new Promise(r => setTimeout(r, 500));
        continue;
      }
      cachedBaseUrl = `${backendUrl}/api`;
      return cachedBaseUrl;
    } catch {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  throw new Error('后端服务未就绪，请重启应用');
}

export async function optimizeBlock(request: OptimizeRequest): Promise<OptimizeResponse> {
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/optimize-block`, {
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
  const apiBase = await getApiBase();
  const response = await fetch(`${apiBase}/optimize-advanced-block`, {
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

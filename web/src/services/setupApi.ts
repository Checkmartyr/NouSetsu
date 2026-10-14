import { API_BASE } from './apiBase';
import type { MachineEnvironment, ModelProvider } from '../types/dashboard';

export interface SetupSnapshot {
  completed: boolean; existing: boolean; locale: 'en' | 'th';
  readiness: 'not_connected' | 'configured' | 'tested' | 'needs_attention';
  provider: ModelProvider; model: string; providers: Record<ModelProvider, boolean>;
  credential_sources?: Partial<Record<ModelProvider, string>>;
  semantic_retrieval: boolean; installation: 'desktop' | 'python';
  values: Record<string, string>; environment: MachineEnvironment; fields: string[]; revision: string;
}
export interface SetupCandidate {
  locale: 'en' | 'th'; provider: ModelProvider; model: string;
  skip_ai: boolean; route_all: boolean; values: Record<string, string>; api_keys: Record<string, string>;
}
export class SetupError extends Error {
  constructor(message: string, public code: string, public field?: string) { super(message); }
}
export async function setupRequest<T>(path: string, body?: unknown, revision?: string): Promise<T> {
  const response = await fetch(`${API_BASE}/api/setup${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...(revision ? { 'If-Match': `"${revision}"` } : {}) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const data = await response.json();
  if (!response.ok) {
    const issue = Array.isArray(data.detail) ? data.detail[0] : undefined;
    throw new SetupError(data.message || issue?.msg || (typeof data.detail === 'string' ? data.detail : 'Could not complete setup.'), response.status === 412 ? 'conflict' : data.code || 'invalid', issue?.loc?.at(-1));
  }
  return data as T;
}

import { Position, Summary, Trade, TradeInput } from './types';

export class ApiError extends Error {}

function buildHeaders(apiKey: string, hasBody: boolean): Record<string, string> {
  const headers: Record<string, string> = {};
  if (hasBody) headers['Content-Type'] = 'application/json';
  if (apiKey) headers['X-API-Key'] = apiKey;
  return headers;
}

async function request<T>(
  baseUrl: string,
  apiKey: string,
  path: string,
  options: RequestInit = {}
): Promise<T> {
  if (!baseUrl) {
    throw new ApiError('설정 탭에서 API 서버 주소를 먼저 입력해주세요.');
  }
  const url = `${baseUrl.replace(/\/$/, '')}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: { ...buildHeaders(apiKey, options.body != null), ...(options.headers as Record<string, string> | undefined) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      if (data && typeof data.detail === 'string') detail = data.detail;
    } catch {
      // 응답 본문이 JSON이 아니면 statusText 그대로 사용
    }
    throw new ApiError(`${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function createApiClient(baseUrl: string, apiKey: string) {
  return {
    health: () => request<{ status: string }>(baseUrl, apiKey, '/health'),
    listTrades: () => request<Trade[]>(baseUrl, apiKey, '/trades'),
    getTrade: (id: number) => request<Trade>(baseUrl, apiKey, `/trades/${id}`),
    createTrade: (trade: TradeInput) =>
      request<{ status: string }>(baseUrl, apiKey, '/trades', {
        method: 'POST',
        body: JSON.stringify(trade),
      }),
    updateTrade: (id: number, trade: TradeInput) =>
      request<{ status: string }>(baseUrl, apiKey, `/trades/${id}`, {
        method: 'PUT',
        body: JSON.stringify(trade),
      }),
    deleteTrade: (id: number) =>
      request<{ status: string }>(baseUrl, apiKey, `/trades/${id}`, { method: 'DELETE' }),
    getPositions: () => request<Position[]>(baseUrl, apiKey, '/analytics/positions'),
    getSummary: () => request<Summary>(baseUrl, apiKey, '/analytics/summary'),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

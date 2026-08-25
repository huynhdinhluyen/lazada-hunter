import {
  ChatRequest,
  ChatResponse,
  ProductListResponse,
  PriceHistoryItem,
  TelegramBotStatus,
} from '../types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      const errorBody = await res.text();
      let errorMsg = `HTTP Error ${res.status}`;
      try {
        const parsed = JSON.parse(errorBody);
        errorMsg = parsed.detail || errorMsg;
      } catch {
        errorMsg = errorBody || errorMsg;
      }
      throw new Error(errorMsg);
    }

    return await res.json();
  } catch (err: any) {
    console.error(`API Fetch Error [${url}]:`, err);
    throw err;
  }
}

export const apiService = {
  // 1. Health Status
  checkHealth: (): Promise<{ status: string; app?: string; version?: string }> => {
    return fetchJSON<{ status: string; app?: string; version?: string }>(`${API_BASE_URL}/health`);
  },

  // 2. AI Shopping Assistant
  sendChatMessage: (data: ChatRequest): Promise<ChatResponse> => {
    return fetchJSON<ChatResponse>(`${API_BASE_URL}/chat`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 3. Product Catalog & Price History
  getProducts: (params: {
    q?: string;
    platform?: string;
    min_price?: number;
    max_price?: number;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }): Promise<ProductListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.q) searchParams.append('q', params.q);
    if (params.platform) searchParams.append('platform', params.platform);
    if (params.min_price !== undefined) searchParams.append('min_price', params.min_price.toString());
    if (params.max_price !== undefined) searchParams.append('max_price', params.max_price.toString());
    if (params.sort_by) searchParams.append('sort_by', params.sort_by);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.page_size) searchParams.append('page_size', params.page_size.toString());

    return fetchJSON<ProductListResponse>(`${API_BASE_URL}/products?${searchParams.toString()}`);
  },

  getPriceHistory: (productId: number): Promise<PriceHistoryItem[]> => {
    return fetchJSON<PriceHistoryItem[]>(`${API_BASE_URL}/products/${productId}/price-history`);
  },

  // 4. Telegram Notification Center
  getTelegramStatus: (): Promise<TelegramBotStatus> => {
    return fetchJSON<TelegramBotStatus>(`${API_BASE_URL}/telegram/status`);
  },

  sendTelegramTest: (chatId?: string): Promise<{ status: string; message: string; details?: any }> => {
    return fetchJSON<{ status: string; message: string; details?: any }>(`${API_BASE_URL}/telegram/test`, {
      method: 'POST',
      body: JSON.stringify(chatId ? { chat_id: chatId } : {}),
    });
  },

  updateTelegramChatId: (chatId?: string): Promise<{ status: string; message: string; chat_id?: string }> => {
    return fetchJSON<{ status: string; message: string; chat_id?: string }>(`${API_BASE_URL}/telegram/chat-id`, {
      method: 'POST',
      body: JSON.stringify(chatId ? { chat_id: chatId } : {}),
    });
  },

  broadcastProductToTelegram: (productId: number, chatId?: string): Promise<{ status: string; message: string }> => {
    const url = chatId
      ? `${API_BASE_URL}/telegram/broadcast-product/${productId}?chat_id=${encodeURIComponent(chatId)}`
      : `${API_BASE_URL}/telegram/broadcast-product/${productId}`;
    return fetchJSON<{ status: string; message: string }>(url, {
      method: 'POST',
    });
  },

  // 6. AI Product Intelligence Engine
  analyzeProduct: (productId: number, autoNotifyTelegram: boolean = false): Promise<any> => {
    return fetchJSON<any>(`${API_BASE_URL}/ai/analyze-product/${productId}?auto_notify_telegram=${autoNotifyTelegram}`, {
      method: 'POST',
    });
  },

  batchAnalyzeProducts: (productIds: number[], autoNotifyTelegram: boolean = false): Promise<any> => {
    return fetchJSON<any>(`${API_BASE_URL}/ai/batch-analyze`, {
      method: 'POST',
      body: JSON.stringify({ product_ids: productIds, auto_notify_telegram: autoNotifyTelegram }),
    });
  },

  // 7. Data Export Helpers
  getExportUrl: (format: 'excel' | 'csv' | 'json', query?: string, platform?: string): string => {
    const params = new URLSearchParams();
    if (query) params.append('q', query);
    if (platform && platform !== 'all') params.append('platform', platform);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    return `${API_BASE_URL}/products/export/${format}${queryString}`;
  },

  // 8. Watchlist (Danh sách sản phẩm theo dõi)
  getWatchlist: (userId: string): Promise<{ items: any[]; total: number }> => {
    return fetchJSON<{ items: any[]; total: number }>(`${API_BASE_URL}/watchlist?user_id=${encodeURIComponent(userId)}`);
  },

  addToWatchlist: (userId: string, productId: number): Promise<{ status: string; message: string }> => {
    return fetchJSON<{ status: string; message: string }>(`${API_BASE_URL}/watchlist`, {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, product_id: productId }),
    });
  },

  removeFromWatchlist: (userId: string, productId: number): Promise<{ status: string; message: string }> => {
    return fetchJSON<{ status: string; message: string }>(`${API_BASE_URL}/watchlist/${productId}?user_id=${encodeURIComponent(userId)}`, {
      method: 'DELETE',
    });
  },

  checkWatchlist: (userId: string, productId: number): Promise<{ is_saved: boolean }> => {
    return fetchJSON<{ is_saved: boolean }>(`${API_BASE_URL}/watchlist/check/${productId}?user_id=${encodeURIComponent(userId)}`);
  },
};


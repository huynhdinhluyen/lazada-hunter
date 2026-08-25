export type Platform = 'lazada' | 'all';

export type IntentType =
  | 'recommendation'
  | 'comparison'
  | 'clarification_needed'
  | 'unrealistic_constraints'
  | 'chitchat_out_of_scope'
  | 'safety_guard';

export interface PriceHistoryItem {
  id?: number;
  product_id?: number;
  price: number;
  original_price: number;
  discount_percentage: number;
  timestamp?: string;
  scraped_at?: string;
}

export interface ProductAIAnalysis {
  normalized_name: string;
  category_standardized: string;
  specs_summary: string[];
  quality_summary: string;
  pros: string[];
  cons: string[];
  sentiment_score: number;
  competitive_price_analysis: string;
  recommended_price_min: number;
  recommended_price_max: number;
  recommended_price_optimal: number;
  target_audience: string;
  buying_verdict: string;
  model_used?: string;
  analyzed_at?: string;
}

export interface Product {
  id: number;
  platform: 'lazada' | string;
  platform_product_id: string;
  sku?: string;
  name: string;
  url: string;
  image_url?: string;
  brand?: string;
  category?: string;
  current_price: number;
  original_price?: number;
  discount_percentage?: number;
  rating_star?: number;
  rating_count?: number;
  historical_sold?: number;
  stock?: number;
  shop_id?: string;
  shop_name?: string;
  shop_location?: string;
  is_official_shop?: boolean;
  ai_analysis?: ProductAIAnalysis;
  created_at?: string;
  updated_at?: string;
  price_history?: PriceHistoryItem[];
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  message: string;
  intent?: IntentType | string;
  cached?: boolean;
  recommended_products?: Product[];
  created_at: string;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  user_id?: string;
  force_refresh?: boolean;
  model?: string;
}

export interface ChatResponse {
  session_id: string;
  intent: IntentType | string;
  message: string;
  cached: boolean;
  recommended_products: Product[];
  comparison_data?: Record<string, any>;
  created_at: string;
}

export interface TelegramBotStatus {
  is_configured: boolean;
  is_connected: boolean;
  error?: string;
  bot_info?: {
    id: number;
    name: string;
    username: string;
    link?: string;
  } | null;
  chat_id?: string | null;
  notify_on_price_drop?: boolean;
  price_drop_threshold?: number;
}

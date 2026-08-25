'use client';

import React from 'react';
import { Bookmark, ExternalLink, Trash2, Star, LineChart, TrendingDown } from 'lucide-react';
import { useWatchlist } from '../../contexts/WatchlistContext';
import { formatPrice, formatNumber, formatDiscount } from '../../utils/formatters';
import { Product } from '../../types';
import { ProductImageThumbnail } from '../common/ProductImageThumbnail';

interface WatchlistPanelProps {
  onViewHistory?: (product: Product) => void;
}

export const WatchlistPanel: React.FC<WatchlistPanelProps> = ({ onViewHistory }) => {
  const { savedItems, savedCount, removeProduct, isLoading } = useWatchlist();

  if (isLoading) {
    return (
      <div className="w-full space-y-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="watchlist-skeleton-card animate-pulse" />
        ))}
      </div>
    );
  }

  if (savedCount === 0) {
    return (
      <div className="watchlist-empty">
        <div className="watchlist-empty-icon">
          <Bookmark className="h-10 w-10 text-indigo-300" />
        </div>
        <h3 className="text-lg font-bold text-slate-800 mt-4">Danh sách theo dõi trống</h3>
        <p className="text-sm text-slate-500 mt-2 max-w-xs text-center leading-relaxed">
          Hãy nhấn nút <strong>Theo dõi</strong> trên bất kỳ sản phẩm nào khi chat với AI hoặc trong Kho Sản Phẩm để bắt đầu theo dõi giá.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bookmark className="h-5 w-5 text-indigo-600" />
          <h2 className="text-base font-bold text-slate-900">Sản Phẩm Đang Theo Dõi</h2>
          <span className="inline-flex items-center justify-center rounded-full bg-indigo-600 px-2 py-0.5 text-xs font-bold text-white">
            {savedCount}
          </span>
        </div>
      </div>

      {/* Watchlist Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {savedItems.map((item) => {
          const prod = item.product;
          if (!prod) return null;
          const discountStr = formatDiscount(prod.discount_percentage);

          return (
            <div
              key={item.id}
              className="watchlist-item-card group"
            >
              {/* Bookmark indicator */}
              <div className="absolute top-2 left-2 z-10">
                <span className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-0.5 text-[10px] font-bold text-white shadow">
                  <Bookmark className="h-3 w-3 fill-white" />
                  Theo dõi
                </span>
              </div>

              {/* Remove button */}
              <button
                onClick={() => removeProduct(prod.id)}
                className="watchlist-remove-btn"
                title="Xóa khỏi danh sách theo dõi"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>

              {/* Image */}
              <div className="relative mt-4 mb-3 h-40 w-full overflow-hidden rounded-xl bg-slate-100 flex items-center justify-center">
                <ProductImageThumbnail src={prod.image_url} alt={prod.name} />
                {discountStr && (
                  <div className="absolute bottom-2 right-2">
                    <span className="inline-flex items-center gap-0.5 rounded-md bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
                      <TrendingDown className="h-3 w-3" />
                      {discountStr}
                    </span>
                  </div>
                )}
              </div>

              {/* Product info */}
              <div className="h-10 sm:h-11 overflow-hidden flex items-start">
                <a
                  href={prod.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="line-clamp-2 text-xs sm:text-sm font-semibold text-slate-900 leading-snug group-hover:text-indigo-600 transition-colors block"
                  title={prod.name}
                >
                  {prod.name}
                </a>
              </div>

              {/* Rating & Sold */}
              <div className="mt-2 flex items-center gap-2 text-xs text-slate-500 min-h-[18px]">
                {prod.rating_star ? (
                  <span className="flex items-center gap-1 text-amber-600 font-semibold">
                    <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                    {prod.rating_star.toFixed(1)}
                  </span>
                ) : (
                  <span className="text-slate-400 text-[11px]">Chưa có đánh giá</span>
                )}
                {prod.historical_sold ? (
                  <span>Đã bán: <strong className="text-slate-700 font-semibold">{formatNumber(prod.historical_sold)}</strong></span>
                ) : null}
              </div>

              {/* Price & Actions */}
              <div className="mt-3 pt-3 border-t border-slate-100 shrink-0">
                <div className="flex items-baseline gap-2 mb-3 min-h-[26px]">
                  <span className="text-base font-black text-emerald-700">
                    {formatPrice(prod.current_price)}
                  </span>
                  {prod.original_price && prod.original_price > prod.current_price && (
                    <span className="text-xs text-slate-400 line-through">
                      {formatPrice(prod.original_price)}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {onViewHistory && (
                    <button
                      onClick={() => onViewHistory(prod)}
                      className="flex-1 flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
                    >
                      <LineChart className="h-3.5 w-3.5 text-indigo-600" />
                      <span>Lịch sử</span>
                    </button>
                  )}
                  <a
                    href={prod.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-1 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 px-2.5 py-1.5 text-xs font-bold text-white hover:from-indigo-700 hover:to-violet-700 transition-all"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    <span>Mở sàn</span>
                  </a>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

'use client';

import React from 'react';
import { Star, Store, TrendingDown, LineChart, Bookmark, Sparkles } from 'lucide-react';
import { Product } from '../../types';
import { formatPrice, formatNumber, formatDiscount } from '../../utils/formatters';
import { ProductImageThumbnail } from '../common/ProductImageThumbnail';
import { useWatchlist } from '../../contexts/WatchlistContext';

interface ProductCardProps {
  product: Product;
  onViewHistory: (product: Product) => void;
  onViewAI?: (product: Product) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({ product, onViewHistory, onViewAI }) => {
  const discountStr = formatDiscount(product.discount_percentage);
  const { isSaved, saveProduct, removeProduct } = useWatchlist();
  const saved = isSaved(product.id);
  const hasAI = Boolean(product.ai_analysis);

  const handleBookmark = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (saved) {
      await removeProduct(product.id);
    } else {
      await saveProduct(product);
    }
  };

  return (
    <div className="product-card group relative flex flex-col justify-between h-full overflow-hidden rounded-3xl border border-slate-200 bg-white p-4 shadow-xs transition-all duration-300 hover:-translate-y-1.5 hover:border-indigo-400/60 hover:shadow-xl hover:shadow-indigo-500/10">
      <div className="flex flex-col flex-1">
        {/* Product Image Thumbnail */}
        <div className="relative mb-3 h-44 w-full overflow-hidden rounded-2xl bg-slate-100 flex items-center justify-center shrink-0">
          <ProductImageThumbnail src={product.image_url} alt={product.name} />

          {/* Discount Tag */}
          {discountStr && (
            <div className="absolute top-2.5 right-2.5">
              <span className="inline-flex items-center gap-0.5 rounded-md bg-rose-600 px-2 py-0.5 text-xs font-bold text-white shadow-xs">
                <TrendingDown className="h-3.5 w-3.5" />
                {discountStr}
              </span>
            </div>
          )}

          {/* AI Badge */}
          {hasAI && (
            <div className="absolute bottom-2.5 left-2.5">
              <span className="inline-flex items-center gap-1 rounded-md bg-amber-500/90 backdrop-blur-xs px-2 py-0.5 text-[10px] font-extrabold text-white shadow-xs">
                <Sparkles className="h-3 w-3" />
                AI: {product.ai_analysis?.sentiment_score.toFixed(1)}/10
              </span>
            </div>
          )}

          {/* Bookmark button */}
          <button
            onClick={handleBookmark}
            className={`bookmark-btn absolute top-2.5 left-2.5 flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-200 ${saved
                ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                : 'bg-white/90 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-indigo-600 shadow-sm'
              }`}
            title={saved ? 'Bỏ theo dõi' : 'Theo dõi sản phẩm này'}
          >
            <Bookmark className={`h-3.5 w-3.5 transition-all ${saved ? 'fill-white' : ''}`} />
          </button>
        </div>

        {/* Product Title (Locked to strictly 2 Lines) */}
        <div className="h-10 sm:h-11 overflow-hidden flex items-start">
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="line-clamp-2 text-xs sm:text-sm font-semibold text-slate-900 leading-snug group-hover:text-indigo-600 transition-colors hover:underline block"
            title={product.name}
          >
            {product.name}
          </a>
        </div>

        {/* Shop Info */}
        <div className="mt-2 flex items-center gap-1.5 text-xs text-slate-500 min-h-[18px]">
          <Store className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span className="truncate">{product.shop_name || 'Gian hàng chính hãng'}</span>
        </div>

        {/* Ratings & Sold Count */}
        <div className="mt-2 flex items-center gap-3 text-xs text-slate-500 min-h-[18px]">
          {product.rating_star ? (
            <span className="flex items-center gap-1 text-amber-600 font-semibold">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              {product.rating_star.toFixed(1)}
              {product.rating_count ? (
                <span className="text-slate-400 font-normal">({formatNumber(product.rating_count)})</span>
              ) : null}
            </span>
          ) : (
            <span className="text-slate-400 text-[11px]">Chưa có đánh giá</span>
          )}
          {product.historical_sold ? (
            <span>
              Đã bán: <strong className="text-slate-800 font-semibold">{formatNumber(product.historical_sold)}</strong>
            </span>
          ) : null}
        </div>
      </div>

      {/* Pricing & Actions */}
      <div className="mt-4 pt-3 border-t border-slate-100 shrink-0">
        <div className="flex items-baseline gap-2 min-h-[26px]">
          <span className="text-base font-black text-emerald-700 sm:text-lg">
            {formatPrice(product.current_price)}
          </span>
          {product.original_price && product.original_price > product.current_price && (
            <span className="text-xs text-slate-400 line-through">
              {formatPrice(product.original_price)}
            </span>
          )}
        </div>

        <div className="mt-3 grid grid-cols-2 gap-1.5">
          {onViewAI && (
            <button
              onClick={() => onViewAI(product)}
              className="flex items-center justify-center gap-1 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-2.5 py-2 text-xs font-bold text-white shadow-xs hover:from-amber-600 hover:to-orange-600 transition-all cursor-pointer"
            >
              <Sparkles className="h-3.5 w-3.5" />
              <span>Phân Tích AI</span>
            </button>
          )}

          <button
            onClick={() => onViewHistory(product)}
            className={`flex items-center justify-center gap-1 rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-100 hover:text-slate-900 cursor-pointer ${!onViewAI ? 'col-span-2' : ''}`}
          >
            <LineChart className="h-3.5 w-3.5 text-indigo-600" />
            <span>Lịch sử giá</span>
          </button>
        </div>
      </div>
    </div>
  );
};


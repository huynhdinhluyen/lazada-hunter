'use client';

import React from 'react';
import { ExternalLink, Star, Store, TrendingDown, Bookmark } from 'lucide-react';
import { Product } from '../../types';
import { formatPrice, formatNumber, formatDiscount } from '../../utils/formatters';
import { ProductImageThumbnail } from '../common/ProductImageThumbnail';
import { useWatchlist } from '../../contexts/WatchlistContext';

interface EmbeddedProductCardProps {
  product: Product;
  onViewHistory?: (product: Product) => void;
}

export const EmbeddedProductCard: React.FC<EmbeddedProductCardProps> = ({
  product,
  onViewHistory,
}) => {
  const discountStr = formatDiscount(product.discount_percentage);
  const { isSaved, saveProduct, removeProduct } = useWatchlist();
  const saved = isSaved(product.id);

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
    <div className="group relative flex flex-col justify-between overflow-hidden rounded-xl border border-slate-200 bg-white p-3 shadow-2xs transition-all duration-200 hover:border-indigo-400 hover:shadow-md hover:-translate-y-0.5">
      <div>
        {/* Product Image & Badges */}
        <div className="relative mb-2.5 h-36 w-full overflow-hidden rounded-lg bg-slate-100 flex items-center justify-center">
          <ProductImageThumbnail src={product.image_url} alt={product.name} />

          {discountStr && (
            <div className="absolute top-2 right-2">
              <span className="inline-flex items-center gap-0.5 rounded-md bg-rose-600 px-1.5 py-0.5 text-[10px] font-bold text-white shadow-xs">
                <TrendingDown className="h-3 w-3" />
                {discountStr}
              </span>
            </div>
          )}

          {/* Bookmark button */}
          <button
            onClick={handleBookmark}
            className={`bookmark-btn absolute top-2 left-2 flex h-6 w-6 items-center justify-center rounded-md transition-all duration-200 ${
              saved
                ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/30'
                : 'bg-white/90 text-slate-400 opacity-0 group-hover:opacity-100 hover:text-indigo-600'
            }`}
            title={saved ? 'Bỏ theo dõi' : 'Theo dõi sản phẩm'}
          >
            <Bookmark className={`h-3 w-3 ${saved ? 'fill-white' : ''}`} />
          </button>
        </div>

        {/* Product Title */}
        <a
          href={product.url}
          target="_blank"
          rel="noopener noreferrer"
          className="line-clamp-2 text-xs font-bold text-slate-900 group-hover:text-indigo-600 transition-colors sm:text-sm hover:underline block"
          title={product.name}
        >
          {product.name}
        </a>

        {/* Shop Info */}
        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
          <Store className="h-3 w-3 text-slate-400 shrink-0" />
          <span className="truncate">{product.shop_name || 'Gian hàng chính hãng'}</span>
        </div>

        {/* Ratings & Sold Count */}
        <div className="mt-1.5 flex items-center gap-3 text-xs text-slate-500">
          {product.rating_star ? (
            <span className="flex items-center gap-1 text-amber-600 font-medium">
              <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
              {product.rating_star.toFixed(1)}
            </span>
          ) : null}
          {product.historical_sold ? (
            <span>Đã bán: <strong className="text-slate-700 font-semibold">{formatNumber(product.historical_sold)}</strong></span>
          ) : null}
        </div>
      </div>

      {/* Pricing & CTA */}
      <div className="mt-3 pt-2.5 border-t border-slate-100">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-black text-emerald-700 sm:text-base">
            {formatPrice(product.current_price)}
          </span>
          {product.original_price && product.original_price > product.current_price && (
            <span className="text-xs text-slate-400 line-through">
              {formatPrice(product.original_price)}
            </span>
          )}
        </div>

        <div className="mt-2.5 flex items-center gap-1.5">
          {onViewHistory && (
            <button
              onClick={() => onViewHistory(product)}
              className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-center text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
            >
              Lịch sử giá
            </button>
          )}
          {/* Bookmark button (text version in CTA row) */}
          <button
            onClick={handleBookmark}
            className={`flex items-center justify-center gap-1 rounded-lg px-2 py-1.5 text-xs font-bold transition-all cursor-pointer ${
              saved
                ? 'bg-indigo-100 text-indigo-700 border border-indigo-300'
                : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200'
            }`}
            title={saved ? 'Bỏ theo dõi' : 'Lưu theo dõi'}
          >
            <Bookmark className={`h-3.5 w-3.5 ${saved ? 'fill-indigo-600' : ''}`} />
          </button>
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white transition-colors hover:bg-indigo-700 shadow-xs"
          >
            <span>Xem</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </div>
  );
};

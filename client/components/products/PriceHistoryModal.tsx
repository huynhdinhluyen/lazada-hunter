import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { X, ExternalLink, Loader2, DollarSign } from 'lucide-react';
import { Product, PriceHistoryItem } from '../../types';
import { apiService } from '../../services/api';
import { formatPrice } from '../../utils/formatters';

interface PriceHistoryModalProps {
  product: Product | null;
  onClose: () => void;
}

export const PriceHistoryModal: React.FC<PriceHistoryModalProps> = ({
  product,
  onClose,
}) => {
  const [history, setHistory] = useState<PriceHistoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!product) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, [product]);

  useEffect(() => {
    if (!product) return;

    const fetchHistory = async () => {
      setIsLoading(true);
      try {
        const data = await apiService.getPriceHistory(product.id);
        setHistory(data);
      } catch (err) {
        console.error('Lỗi khi lấy lịch sử giá:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchHistory();
  }, [product]);

  if (!mounted || !product) return null;

  const prices = history.map((h) => h.price);
  const minPrice = prices.length > 0 ? Math.min(...prices) : product.current_price;
  const maxPrice = prices.length > 0 ? Math.max(...prices) : product.current_price;
  const priceDiff = maxPrice - minPrice;

  const modalContent = (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
      <div className="relative flex flex-col w-full max-w-2xl max-h-[90vh] sm:max-h-[85vh] overflow-hidden rounded-2xl sm:rounded-3xl border border-slate-200 bg-white shadow-2xl my-auto">
        {/* Header */}
        <div className="shrink-0 flex items-center justify-between border-b border-slate-100 bg-slate-50 px-6 py-4">
          <div className="flex items-center gap-2">
            <DollarSign className="h-5 w-5 text-emerald-600" />
            <h3 className="text-base font-bold text-slate-900">Biểu Đồ Lịch Sử Biến Động Giá</h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-800 transition-colors cursor-pointer"
            title="Đóng"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-6 space-y-5">
          {/* Product Summary */}
          <div className="flex items-start gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="truncate text-xs font-semibold text-slate-600">{product.shop_name}</span>
              </div>
              <h4 className="line-clamp-2 text-sm font-semibold text-slate-900">{product.name}</h4>
              <div className="mt-2 flex items-baseline gap-2">
                <span className="text-lg font-bold text-emerald-700">
                  {formatPrice(product.current_price)}
                </span>
                {product.original_price && product.original_price > product.current_price && (
                  <span className="text-xs text-slate-400 line-through">
                    {formatPrice(product.original_price)}
                  </span>
                )}
              </div>
            </div>

            <a
              href={product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex shrink-0 items-center gap-1 rounded-xl bg-indigo-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-indigo-700 transition-colors shadow-xs"
            >
              Xem trên sàn
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </div>

          {/* Stats Badges */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-slate-200 bg-emerald-50/50 p-3 text-center">
              <span className="text-[11px] font-semibold text-emerald-800">Giá Thấp Nhất</span>
              <p className="mt-1 text-sm font-black text-emerald-700">{formatPrice(minPrice)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-rose-50/50 p-3 text-center">
              <span className="text-[11px] font-semibold text-rose-800">Giá Cao Nhất</span>
              <p className="mt-1 text-sm font-black text-rose-700">{formatPrice(maxPrice)}</p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-indigo-50/50 p-3 text-center">
              <span className="text-[11px] font-semibold text-indigo-800">Chênh Lệch</span>
              <p className="mt-1 text-sm font-black text-indigo-700">{formatPrice(priceDiff)}</p>
            </div>
          </div>

          {/* SVG Price Chart */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-bold text-slate-800">Biểu đồ xu hướng giá:</span>
              <span className="text-[11px] font-medium text-slate-500">{history.length} mốc ghi nhận</span>
            </div>

            {isLoading ? (
              <div className="flex h-44 items-center justify-center text-slate-500">
                <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
                <span className="ml-2 text-xs">Đang tải biểu đồ...</span>
              </div>
            ) : history.length === 0 ? (
              <div className="flex h-44 items-center justify-center text-xs text-slate-400">
                Chưa có dữ liệu biến động giá đa mốc. Sản phẩm đang ở mức giá ban đầu.
              </div>
            ) : (
              <div className="relative h-44 w-full">
                <svg className="h-full w-full overflow-visible" viewBox="0 0 500 120">
                  <line x1="0" y1="20" x2="500" y2="20" stroke="#e2e8f0" strokeDasharray="3 3" />
                  <line x1="0" y1="60" x2="500" y2="60" stroke="#e2e8f0" strokeDasharray="3 3" />
                  <line x1="0" y1="100" x2="500" y2="100" stroke="#e2e8f0" strokeDasharray="3 3" />

                  {(() => {
                    const points = history.map((item, idx) => {
                      const x = history.length > 1 ? (idx / (history.length - 1)) * 480 + 10 : 250;
                      const range = maxPrice - minPrice || 1;
                      const y = 100 - ((item.price - minPrice) / range) * 80;
                      return `${x},${y}`;
                    });

                    return (
                      <>
                        <polyline
                          fill="none"
                          stroke="#4f46e5"
                          strokeWidth="3"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          points={points.join(' ')}
                        />
                        {history.map((item, idx) => {
                          const x = history.length > 1 ? (idx / (history.length - 1)) * 480 + 10 : 250;
                          const range = maxPrice - minPrice || 1;
                          const y = 100 - ((item.price - minPrice) / range) * 80;
                          return (
                            <g key={idx}>
                              <circle cx={x} cy={y} r="5" fill="#6366f1" stroke="#ffffff" strokeWidth="2" />
                            </g>
                          );
                        })}
                      </>
                    );
                  })()}
                </svg>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-slate-100 bg-slate-50 px-6 py-3 text-right">
          <button
            onClick={onClose}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 shadow-2xs hover:bg-slate-100 cursor-pointer"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
};

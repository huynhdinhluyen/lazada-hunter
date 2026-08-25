'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Search,
  Loader2,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  ShoppingBag,
  X,
  LayoutGrid,
  Table as TableIcon,
  Download,
  FileSpreadsheet,
  FileText,
  FileCode,
  Sparkles,
  Send,
  LineChart,
  ExternalLink,
  Filter,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { Product } from '../../types';
import { apiService } from '../../services/api';
import { ProductCard } from './ProductCard';
import { PriceHistoryModal } from './PriceHistoryModal';
import { AIAnalysisModal } from './AIAnalysisModal';
import { formatPrice, formatNumber, formatDiscount } from '../../utils/formatters';
import { ProductImageThumbnail } from '../common/ProductImageThumbnail';

const DEBOUNCE_MS = 400;
type ViewMode = 'grid' | 'table';

export const ProductCatalog: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [sortBy, setSortBy] = useState<string>('created_desc');
  const [aiFilter, setAiFilter] = useState<string>('all'); // 'all' | 'has_ai' | 'no_ai'
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [isLoading, setIsLoading] = useState(false);

  // Modals state
  const [selectedProductForHistory, setSelectedProductForHistory] = useState<Product | null>(null);
  const [selectedProductForAI, setSelectedProductForAI] = useState<Product | null>(null);

  // Quick Action States
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{ id: number; message: string; isError?: boolean } | null>(null);
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchProducts = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await apiService.getProducts({
        q: debouncedQuery,
        platform: 'all',
        sort_by: sortBy,
        page: page,
        page_size: viewMode === 'table' ? 15 : 12,
      });

      let items = res.items;
      if (aiFilter === 'has_ai') {
        items = items.filter((p) => Boolean(p.ai_analysis));
      } else if (aiFilter === 'no_ai') {
        items = items.filter((p) => !p.ai_analysis);
      }

      setProducts(items);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      console.error('Lỗi khi tải danh sách sản phẩm:', err);
    } finally {
      setIsLoading(false);
    }
  }, [debouncedQuery, sortBy, page, viewMode, aiFilter]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const clearSearch = () => {
    setSearchQuery('');
    inputRef.current?.focus();
  };

  // Quick 1-click broadcast to Telegram
  const handleQuickTelegram = async (product: Product) => {
    setActionLoadingId(product.id);
    setActionFeedback(null);
    try {
      await apiService.broadcastProductToTelegram(product.id);
      setActionFeedback({ id: product.id, message: 'Đã bắn lên Telegram!' });
      setTimeout(() => setActionFeedback(null), 3000);
    } catch (err: any) {
      setActionFeedback({ id: product.id, message: 'Lỗi gửi Telegram', isError: true });
      setTimeout(() => setActionFeedback(null), 3500);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Quick 1-click AI Analyze
  const handleQuickAI = async (product: Product) => {
    setActionLoadingId(product.id);
    setActionFeedback(null);
    try {
      const aiResult = await apiService.analyzeProduct(product.id, false);
      const updated = { ...product, ai_analysis: aiResult };
      setProducts((prev) => prev.map((p) => (p.id === product.id ? updated : p)));
      setSelectedProductForAI(updated);
    } catch (err: any) {
      alert(`Lỗi AI: ${err.message || 'Không xác định'}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Batch analyze current page
  const handleBatchAnalyze = async () => {
    const unanalyzedIds = products.filter((p) => !p.ai_analysis).map((p) => p.id);
    if (unanalyzedIds.length === 0) {
      alert('Tất cả sản phẩm trên trang này đã được AI phân tích!');
      return;
    }
    setIsBatchAnalyzing(true);
    try {
      await apiService.batchAnalyzeProducts(unanalyzedIds, false);
      fetchProducts();
      alert(`Đã hoàn tất phân tích AI cho ${unanalyzedIds.length} sản phẩm!`);
    } catch (err: any) {
      alert(`Lỗi phân tích hàng loạt: ${err.message}`);
    } finally {
      setIsBatchAnalyzing(false);
    }
  };

  // Export handlers
  const triggerExport = (format: 'excel' | 'csv' | 'json') => {
    const exportUrl = apiService.getExportUrl(format, debouncedQuery, 'all');
    window.open(exportUrl, '_blank');
  };

  return (
    <div className="w-full space-y-5">
      {/* Top Search, View Switcher & Export Toolbar */}
      <div className="flex flex-col gap-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Search Input with Debounce */}
          <div className="relative flex-1 max-w-lg">
            <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              ref={inputRef}
              type="text"
              id="catalog-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Tìm theo tên sản phẩm, thương hiệu... (tìm tức thì)"
              className="w-full rounded-2xl border border-slate-300 bg-slate-50 pl-10 pr-10 py-2.5 text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-600/20 shadow-2xs transition-all"
            />
            {isLoading ? (
              <Loader2 className="absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-500 animate-spin" />
            ) : searchQuery && (
              <button
                onClick={clearSearch}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Export Toolbar */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-bold text-slate-500 mr-1 hidden sm:inline">
              Xuất dữ liệu:
            </span>
            <button
              onClick={() => triggerExport('excel')}
              className="flex items-center gap-1.5 rounded-xl border border-emerald-300 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-800 hover:bg-emerald-100 shadow-2xs cursor-pointer transition-colors"
              title="Xuất file Excel (.xlsx) có định dạng bảng"
            >
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-600" />
              <span>Excel</span>
            </button>
            <button
              onClick={() => triggerExport('csv')}
              className="flex items-center gap-1.5 rounded-xl border border-blue-300 bg-blue-50 px-3 py-2 text-xs font-bold text-blue-800 hover:bg-blue-100 shadow-2xs cursor-pointer transition-colors"
              title="Xuất file CSV (chuẩn UTF-8 BOM tiếng Việt)"
            >
              <FileText className="h-3.5 w-3.5 text-blue-600" />
              <span>CSV</span>
            </button>
            <button
              onClick={() => triggerExport('json')}
              className="flex items-center gap-1.5 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-bold text-amber-800 hover:bg-amber-100 shadow-2xs cursor-pointer transition-colors"
              title="Xuất file JSON có cấu trúc đầy đủ AI insights"
            >
              <FileCode className="h-3.5 w-3.5 text-amber-600" />
              <span>JSON</span>
            </button>
          </div>
        </div>

        {/* Filters & View Toggle Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 text-xs">
          <div className="flex flex-wrap items-center gap-3">
            {/* View Mode Toggle */}
            <div className="flex items-center rounded-xl bg-slate-100 p-1 border border-slate-200">
              <button
                onClick={() => setViewMode('table')}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 font-bold transition-all cursor-pointer ${
                  viewMode === 'table'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <TableIcon className="h-3.5 w-3.5" />
                <span>Dạng Bảng</span>
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 font-bold transition-all cursor-pointer ${
                  viewMode === 'grid'
                    ? 'bg-white text-indigo-700 shadow-xs'
                    : 'text-slate-500 hover:text-slate-900'
                }`}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span>Dạng Thẻ</span>
              </button>
            </div>

            {/* AI Status Filter */}
            <div className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-slate-50 px-3 py-1.5 text-slate-700">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              <select
                value={aiFilter}
                onChange={(e) => {
                  setAiFilter(e.target.value);
                  setPage(1);
                }}
                className="bg-transparent text-xs text-slate-800 font-semibold focus:outline-none cursor-pointer"
              >
                <option value="all">Tất cả sản phẩm</option>
                <option value="has_ai">✨ Đã có phân tích AI</option>
                <option value="no_ai">⏳ Chưa phân tích AI</option>
              </select>
            </div>

            {/* Sort Dropdown */}
            <div className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-slate-50 px-3 py-1.5 text-slate-700">
              <ArrowUpDown className="h-3.5 w-3.5 text-indigo-600" />
              <select
                value={sortBy}
                onChange={(e) => {
                  setSortBy(e.target.value);
                  setPage(1);
                }}
                className="bg-transparent text-xs text-slate-800 font-semibold focus:outline-none cursor-pointer"
              >
                <option value="created_desc">Mới cập nhật nhất</option>
                <option value="sold_desc">Bán chạy nhất</option>
                <option value="price_asc">Giá: Thấp đến Cao</option>
                <option value="price_desc">Giá: Cao đến Thấp</option>
                <option value="rating_desc">Đánh giá sao cao nhất</option>
              </select>
            </div>
          </div>

          {/* Batch Analyze action */}
          <button
            onClick={handleBatchAnalyze}
            disabled={isBatchAnalyzing || products.length === 0}
            className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-1.5 text-xs font-bold text-white shadow-xs hover:from-amber-600 hover:to-orange-600 disabled:opacity-50 cursor-pointer transition-all"
          >
            <Sparkles className={`h-3.5 w-3.5 ${isBatchAnalyzing ? 'animate-spin' : ''}`} />
            <span>{isBatchAnalyzing ? 'Đang chạy AI...' : 'Phân Tích AI Toàn Trang'}</span>
          </button>
        </div>
      </div>

      {/* Catalog Status Info */}
      <div className="flex items-center justify-between text-xs text-slate-500 px-1">
        <span>
          {debouncedQuery ? (
            <>
              Tìm thấy <strong className="text-indigo-600 font-bold">{total}</strong> sản phẩm cho "
              <strong>{debouncedQuery}</strong>"
            </>
          ) : (
            <>
              Hiển thị <strong className="text-slate-900 font-bold">{products.length}</strong> /{' '}
              <strong className="text-slate-900 font-bold">{total}</strong> sản phẩm trên sàn Lazada
            </>
          )}
        </span>
        {isLoading && (
          <div className="flex items-center gap-1.5 text-indigo-600 font-medium">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Đang nạp dữ liệu...</span>
          </div>
        )}
      </div>

      {/* Empty State */}
      {products.length === 0 && !isLoading ? (
        <div className="flex flex-col items-center justify-center rounded-3xl border border-slate-200 bg-white py-16 text-center shadow-xs">
          <ShoppingBag className="h-12 w-12 text-slate-300 mb-3" />
          <h3 className="text-base font-bold text-slate-800">
            {debouncedQuery ? 'Không tìm thấy sản phẩm phù hợp' : 'Chưa có sản phẩm nào trong kho'}
          </h3>
          <p className="mt-1 text-xs text-slate-500 max-w-sm">
            {debouncedQuery
              ? 'Thử thay đổi từ khóa hoặc xóa bộ lọc để tìm lại.'
              : 'Chuyển sang tab Thu Thập Dữ Liệu để bắt đầu cào sản phẩm từ Lazada.'}
          </p>
        </div>
      ) : viewMode === 'table' ? (
        /* TABLE VIEW (Bảng Dữ Liệu Chuyên Nghiệp) */
        <div className="overflow-x-auto rounded-3xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3.5 w-16">Ảnh</th>
                <th className="px-4 py-3.5 min-w-[220px]">Tên Sản Phẩm / Chuẩn Hóa AI</th>
                <th className="px-4 py-3.5 min-w-[130px]">Giá Hiện Tại</th>
                <th className="px-4 py-3.5">Đã Bán</th>
                <th className="px-4 py-3.5">Đánh Giá</th>
                <th className="px-4 py-3.5 min-w-[140px]">Trí Tuệ Nhân Tạo (AI)</th>
                <th className="px-4 py-3.5 text-center min-w-[180px]">Thao Tác Nghiệp Vụ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {products.map((p) => {
                const hasAI = Boolean(p.ai_analysis);
                const discount = formatDiscount(p.discount_percentage);
                const isItemLoading = actionLoadingId === p.id;
                const feedback = actionFeedback?.id === p.id ? actionFeedback : null;

                return (
                  <tr key={p.id} className="hover:bg-slate-50/80 transition-colors">
                    {/* Thumbnail */}
                    <td className="px-4 py-3">
                      <div className="h-12 w-12 overflow-hidden rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center">
                        <ProductImageThumbnail src={p.image_url} alt={p.name} />
                      </div>
                    </td>

                    {/* Name & Normalized */}
                    <td className="px-4 py-3">
                      {p.ai_analysis?.normalized_name && (
                        <div className="flex items-center gap-1 text-[11px] font-bold text-indigo-700 mb-0.5 line-clamp-1">
                          <Sparkles className="h-3 w-3 text-amber-500 shrink-0" />
                          <span>{p.ai_analysis.normalized_name}</span>
                        </div>
                      )}
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-slate-900 hover:text-indigo-600 line-clamp-2 transition-colors block"
                        title={p.name}
                      >
                        {p.name}
                      </a>
                      <span className="text-[10px] text-slate-400 mt-0.5 block truncate">
                        {p.shop_name || 'Gian hàng Lazada'}
                      </span>
                    </td>

                    {/* Price */}
                    <td className="px-4 py-3">
                      <div className="font-bold text-emerald-700 text-xs sm:text-sm">
                        {formatPrice(p.current_price)}
                      </div>
                      {p.original_price && p.original_price > p.current_price && (
                        <div className="flex items-center gap-1 text-[11px] text-slate-400">
                          <span className="line-through">{formatPrice(p.original_price)}</span>
                          {discount && (
                            <span className="text-[10px] font-bold text-rose-600">{discount}</span>
                          )}
                        </div>
                      )}
                    </td>

                    {/* Sold */}
                    <td className="px-4 py-3 font-semibold text-slate-800">
                      {formatNumber(p.historical_sold || 0)}
                    </td>

                    {/* Rating */}
                    <td className="px-4 py-3">
                      {p.rating_star ? (
                        <div className="flex items-center gap-1 text-amber-600 font-bold">
                          <span>{p.rating_star.toFixed(1)}★</span>
                          {p.rating_count ? (
                            <span className="text-[10px] font-normal text-slate-400">
                              ({formatNumber(p.rating_count)})
                            </span>
                          ) : null}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-[11px]">N/A</span>
                      )}
                    </td>

                    {/* AI Status */}
                    <td className="px-4 py-3">
                      {hasAI ? (
                        <button
                          onClick={() => setSelectedProductForAI(p)}
                          className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1 text-[11px] font-bold text-amber-800 border border-amber-200 hover:bg-amber-100 transition-colors cursor-pointer"
                        >
                          <Sparkles className="h-3 w-3 text-amber-600" />
                          <span>Score: {p.ai_analysis?.sentiment_score.toFixed(1)}/10</span>
                        </button>
                      ) : (
                        <button
                          onClick={() => handleQuickAI(p)}
                          disabled={isItemLoading}
                          className="flex items-center gap-1 rounded-lg bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-indigo-50 hover:text-indigo-600 transition-colors cursor-pointer"
                        >
                          {isItemLoading ? (
                            <Loader2 className="h-3 w-3 animate-spin text-indigo-600" />
                          ) : (
                            <Sparkles className="h-3 w-3" />
                          )}
                          <span>Chạy AI</span>
                        </button>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3">
                      {feedback ? (
                        <div
                          className={`text-center py-1 rounded-lg text-[11px] font-bold ${
                            feedback.isError ? 'bg-rose-50 text-rose-700' : 'bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {feedback.message}
                        </div>
                      ) : (
                        <div className="flex items-center justify-center gap-1.5">
                          {/* AI Modal Trigger */}
                          <button
                            onClick={() => setSelectedProductForAI(p)}
                            className="p-1.5 rounded-lg bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 cursor-pointer transition-colors shadow-2xs"
                            title="Xem chi tiết phân tích AI & JSON"
                          >
                            <Sparkles className="h-4 w-4" />
                          </button>

                          {/* Telegram Broadcast */}
                          <button
                            onClick={() => handleQuickTelegram(p)}
                            disabled={isItemLoading}
                            className="p-1.5 rounded-lg bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 cursor-pointer transition-colors shadow-2xs disabled:opacity-50"
                            title="Bắn bản tin tóm tắt sản phẩm lên Telegram"
                          >
                            {isItemLoading ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Send className="h-4 w-4" />
                            )}
                          </button>

                          {/* Price History */}
                          <button
                            onClick={() => setSelectedProductForHistory(p)}
                            className="p-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 cursor-pointer transition-colors"
                            title="Xem lịch sử biến động giá"
                          >
                            <LineChart className="h-4 w-4" />
                          </button>

                          {/* Lazada link */}
                          <a
                            href={p.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="p-1.5 rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors"
                            title="Mở trên Lazada"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* GRID VIEW (Dạng Thẻ) */
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 items-stretch">
          {products.map((prod, i) => (
            <div
              key={prod.id}
              className="animate-fadeIn h-full flex flex-col"
              style={{ animationDelay: `${Math.min(i * 30, 200)}ms` }}
            >
              <ProductCard
                product={prod}
                onViewHistory={(p) => setSelectedProductForHistory(p)}
                onViewAI={(p) => setSelectedProductForAI(p)}
              />
            </div>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && !isLoading && (
        <div className="flex items-center justify-center gap-2 pt-2">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            «
          </button>
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            <ChevronLeft className="h-4 w-4" />
            <span className="hidden sm:inline">Trước</span>
          </button>

          {/* Page numbers */}
          <div className="flex items-center gap-1">
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let pageNum: number;
              if (totalPages <= 7) pageNum = i + 1;
              else if (page <= 4) pageNum = i + 1;
              else if (page >= totalPages - 3) pageNum = totalPages - 6 + i;
              else pageNum = page - 3 + i;

              return (
                <button
                  key={pageNum}
                  onClick={() => setPage(pageNum)}
                  className={`h-8 w-8 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    pageNum === page
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/20'
                      : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {pageNum}
                </button>
              );
            })}
          </div>

          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="flex items-center gap-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            <span className="hidden sm:inline">Sau</span>
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages}
            className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-bold text-slate-700 shadow-2xs hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            »
          </button>
        </div>
      )}

      {/* Price History Modal */}
      <PriceHistoryModal
        product={selectedProductForHistory}
        onClose={() => setSelectedProductForHistory(null)}
      />

      {/* AI Analysis Modal */}
      <AIAnalysisModal
        product={selectedProductForAI}
        onClose={() => setSelectedProductForAI(null)}
        onAnalysisUpdated={(updated) => {
          setProducts((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
          setSelectedProductForAI(updated);
        }}
      />
    </div>
  );
};

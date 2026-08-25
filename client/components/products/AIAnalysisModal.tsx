'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Send,
  Loader2,
  ExternalLink,
  Tag,
  ThumbsUp,
  Target,
  RotateCcw,
  Bot
} from 'lucide-react';
import { Product, ProductAIAnalysis } from '../../types';
import { apiService } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';

interface AIAnalysisModalProps {
  product: Product | null;
  onClose: () => void;
  onAnalysisUpdated?: (updatedProduct: Product) => void;
}

export const AIAnalysisModal: React.FC<AIAnalysisModalProps> = ({
  product,
  onClose,
  onAnalysisUpdated,
}) => {
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [isBroadcasting, setIsBroadcasting] = useState(false);
  const [broadcastStatus, setBroadcastStatus] = useState<string | null>(null);
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

  if (!mounted || !product) return null;

  const ai: ProductAIAnalysis | undefined = product.ai_analysis;

  const handleReanalyze = async () => {
    setIsReanalyzing(true);
    setBroadcastStatus(null);
    try {
      const newAnalysis = await apiService.analyzeProduct(product.id, false);
      const updated = { ...product, ai_analysis: newAnalysis };
      if (onAnalysisUpdated) onAnalysisUpdated(updated);
    } catch (err: any) {
      alert(`Lỗi khi phân tích AI: ${err.message || 'Không xác định'}`);
    } finally {
      setIsReanalyzing(false);
    }
  };

  const handleBroadcastTelegram = async () => {
    setIsBroadcasting(true);
    setBroadcastStatus(null);
    try {
      const res = await apiService.broadcastProductToTelegram(product.id);
      setBroadcastStatus('✅ Đã gửi bản tin tóm tắt sản phẩm lên nhóm Telegram thành công!');
    } catch (err: any) {
      setBroadcastStatus(`❌ Lỗi gửi Telegram: ${err.message || 'Chưa cấu hình Telegram Bot'}`);
    } finally {
      setIsBroadcasting(false);
    }
  };

  const modalContent = (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-3 sm:p-6 backdrop-blur-sm">
      <div className="relative flex flex-col w-full max-w-4xl max-h-[88vh] sm:max-h-[85vh] rounded-2xl sm:rounded-3xl border border-slate-200 bg-white shadow-2xl overflow-hidden my-auto">
        {/* Modal Header */}
        <div className="shrink-0 flex items-center justify-between border-b border-slate-100 bg-gradient-to-r from-indigo-900 via-indigo-800 to-slate-900 px-4 py-3 sm:px-6 sm:py-4 text-white">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-md shadow-amber-500/20 text-white font-bold shrink-0">
              <Sparkles className="h-4.5 w-4.5 sm:h-5 sm:w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-bold sm:text-base truncate">
                AI Product Intelligence &amp; Normalization
              </h2>
              <p className="text-xs text-indigo-200 line-clamp-2 max-w-xl" title={product.name}>
                {product.name}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-xl p-1.5 sm:p-2 text-indigo-200 hover:bg-white/10 hover:text-white transition-colors cursor-pointer shrink-0"
            title="Đóng"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain p-4 sm:p-6 space-y-5">
          {!ai && !isReanalyzing ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bot className="h-16 w-16 text-indigo-300 mb-3 animate-pulse" />
              <h3 className="text-base font-bold text-slate-800">
                Sản phẩm này chưa được AI phân tích
              </h3>
              <p className="text-xs text-slate-500 max-w-md mt-1 mb-4">
                Nhấn nút bên dưới để LLM tự động bóc tách ưu/nhược điểm từ đánh giá khách hàng, chuẩn hóa nội dung và gợi ý mức giá cạnh tranh.
              </p>
              <button
                onClick={handleReanalyze}
                className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md hover:bg-indigo-700 cursor-pointer transition-all"
              >
                <Sparkles className="h-4 w-4" />
                <span>Kích hoạt AI Phân Tích Ngay</span>
              </button>
            </div>
          ) : isReanalyzing ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Loader2 className="h-12 w-12 text-indigo-600 animate-spin mb-3" />
              <h3 className="text-sm font-bold text-slate-800">
                AI Engine đang bóc tách &amp; phân tích chuyên sâu...
              </h3>
              <p className="text-xs text-slate-500 mt-1">
                Đang đối chiếu reviews, chuẩn hóa thông số và tính toán khoảng giá tối ưu qua NVIDIA NIM.
              </p>
            </div>
          ) : ai ? (
            <div className="space-y-5">
              {/* Product Normalized Header & Score */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="sm:col-span-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="rounded-md bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-700 uppercase">
                      {ai.category_standardized || 'Công nghệ'}
                    </span>
                    <span className="text-xs text-slate-500">Tên chuẩn hóa AI:</span>
                  </div>
                  <h3 className="text-sm sm:text-base font-bold text-slate-900 line-clamp-2" title={ai.normalized_name}>
                    {ai.normalized_name}
                  </h3>
                  <div className="mt-3 flex flex-wrap gap-4 text-xs">
                    <div>
                      <span className="text-slate-500">Giá hiện tại: </span>
                      <strong className="text-indigo-600 font-bold">
                        {formatCurrency(product.current_price)}
                      </strong>
                    </div>
                    {product.original_price && product.original_price > product.current_price && (
                      <div>
                        <span className="text-slate-500">Giá niêm yết: </span>
                        <span className="line-through text-slate-400">
                          {formatCurrency(product.original_price)}
                        </span>
                      </div>
                    )}
                    <div>
                      <span className="text-slate-500">Đã bán: </span>
                      <strong className="text-slate-800">{product.historical_sold || 0}</strong>
                    </div>
                    <div>
                      <span className="text-slate-500">Đánh giá: </span>
                      <strong className="text-amber-600">{product.rating_star || 0}★</strong>
                    </div>
                  </div>
                </div>

                {/* Sentiment & Quality Score */}
                <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-orange-50 p-4 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-amber-900">Điểm Đánh Giá AI</span>
                    <ThumbsUp className="h-4 w-4 text-amber-600" />
                  </div>
                  <div className="my-2 flex items-baseline gap-1">
                    <span className="text-3xl font-black text-amber-800">
                      {ai.sentiment_score.toFixed(1)}
                    </span>
                    <span className="text-xs font-semibold text-amber-600">/ 10</span>
                  </div>
                  <div className="w-full bg-amber-200 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-amber-600 h-2 rounded-full transition-all duration-1000"
                      style={{ width: `${Math.min(ai.sentiment_score * 10, 100)}%` }}
                    />
                  </div>
                  <span className="text-[11px] text-amber-800 font-medium mt-1 truncate">
                    {ai.buying_verdict || 'Đáng mua'}
                  </span>
                </div>
              </div>

              {/* Quality Summary */}
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
                <div className="flex items-center gap-2 mb-2">
                  <Sparkles className="h-4 w-4 text-indigo-600" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    Tóm Tắt Chất Lượng Sản Phẩm (Quality Summary)
                  </h4>
                </div>
                <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
                  {ai.quality_summary}
                </p>
              </div>

              {/* Pros & Cons Columns */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Pros */}
                <div className="rounded-2xl border border-emerald-200 bg-emerald-50/50 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-900">
                      Ưu Điểm Nổi Bật (Từ Reviews & Specs)
                    </h4>
                  </div>
                  <ul className="space-y-2">
                    {ai.pros.map((pro, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-xs text-emerald-950 font-medium">
                        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-emerald-200 text-emerald-800 text-[10px] font-bold mt-0.5">
                          ✓
                        </span>
                        <span>{pro}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Cons */}
                <div className="rounded-2xl border border-rose-200 bg-rose-50/50 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="h-4 w-4 text-rose-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-rose-900">
                      Nhược Điểm / Điểm Cần Lưu Ý
                    </h4>
                  </div>
                  <ul className="space-y-2">
                    {ai.cons.map((con, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-xs text-rose-950 font-medium">
                        <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-rose-200 text-rose-800 text-[10px] font-bold mt-0.5">
                          !
                        </span>
                        <span>{con}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Competitive Price Suggestion Box */}
              <div className="rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50/70 to-blue-50/70 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Tag className="h-4 w-4 text-indigo-700" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-900">
                    Gợi Ý Định Giá Cạnh Tranh Thị Trường (AI Price Suggestion)
                  </h4>
                </div>
                <p className="text-xs text-slate-700 mb-3">
                  {ai.competitive_price_analysis}
                </p>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div className="rounded-xl border border-slate-200 bg-white p-2.5">
                    <span className="block text-[11px] text-slate-500 font-medium">Giá Min Khuyến Nghị</span>
                    <strong className="text-xs sm:text-sm font-bold text-slate-700">
                      {formatCurrency(ai.recommended_price_min)}
                    </strong>
                  </div>
                  <div className="rounded-xl border-2 border-indigo-600 bg-indigo-600/10 p-2.5 shadow-xs">
                    <span className="block text-[11px] text-indigo-700 font-bold">Mức Giá Tối Ưu Nhất</span>
                    <strong className="text-xs sm:text-sm font-black text-indigo-700">
                      {formatCurrency(ai.recommended_price_optimal)}
                    </strong>
                  </div>
                  <div className="rounded-xl border border-slate-200 bg-white p-2.5">
                    <span className="block text-[11px] text-slate-500 font-medium">Giá Max Khuyến Nghị</span>
                    <strong className="text-xs sm:text-sm font-bold text-slate-700">
                      {formatCurrency(ai.recommended_price_max)}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Target Audience & Specs */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="h-4 w-4 text-indigo-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Đối Tượng Phù Hợp
                    </h4>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed">
                    {ai.target_audience}
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <ThumbsUp className="h-4 w-4 text-emerald-600" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      Lời Khuyên Quyết Định
                    </h4>
                  </div>
                  <p className="text-xs text-slate-700 leading-relaxed font-semibold">
                    {ai.buying_verdict}
                  </p>
                </div>
              </div>
            </div>
          ) : null}

          {/* Broadcast status notice */}
          {broadcastStatus && (
            <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-xs font-medium text-indigo-900">
              {broadcastStatus}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="shrink-0 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-slate-50 px-4 py-3 sm:px-6 sm:py-4">
          <div className="flex items-center gap-2">
            <a
              href={product.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              <span>Xem trên Lazada</span>
            </a>
            <button
              onClick={handleReanalyze}
              disabled={isReanalyzing}
              className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 cursor-pointer transition-colors shadow-2xs"
            >
              <RotateCcw className={`h-3.5 w-3.5 ${isReanalyzing ? 'animate-spin' : ''}`} />
              <span>Phân tích lại AI</span>
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleBroadcastTelegram}
              disabled={isBroadcasting || !ai}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2 text-xs font-bold text-white shadow-md shadow-blue-600/20 hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 cursor-pointer transition-all"
            >
              {isBroadcasting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Đang gửi Telegram...</span>
                </>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  <span>Bắn Bản Tin Lên Telegram</span>
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 cursor-pointer transition-colors"
            >
              Đóng
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
};

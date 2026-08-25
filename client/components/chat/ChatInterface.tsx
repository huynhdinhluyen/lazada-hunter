'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Send, RefreshCw, Loader2, Bot, AlertCircle } from 'lucide-react';
import { ChatMessage, Product } from '../../types';
import { apiService } from '../../services/api';
import { ChatMessageItem } from './ChatMessageItem';
import { QuickSuggestions } from './QuickSuggestions';

interface ChatInterfaceProps {
  onViewProductHistory?: (product: Product) => void;
  onRefreshStats?: () => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  onViewProductHistory,
  onRefreshStats,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>('');
  const [quotaWarning, setQuotaWarning] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const newSessionId = 'sess_' + Math.random().toString(36).substring(2, 11);
    setSessionId(newSessionId);

    setMessages([
      {
        id: 'init-1',
        sender: 'assistant',
        message:
          '👋 Xin chào! Tôi là **Trợ lý Săn Deal & Mua Sắm Thông Minh** (Được vận hành bởi AI Dynamic Model Router tốc độ cao).\nTôi có thể giúp bạn:\n- 🔍 Tìm kiếm và đối chiếu giá rẻ nhất từ các gian hàng uy tín trên **Lazada Việt Nam**.\n- 🤖 Tư vấn chọn mua đời máy mới nhất (Google Pixel, iPhone, Samsung, bàn phím, chuột gaming...).\n- ⚠️ Cảnh báo mức giá bất thường và gợi ý giải pháp tối ưu ngân sách.\n\nHãy nhập câu hỏi hoặc chọn một trong các gợi ý bên dưới để bắt đầu!',
        created_at: new Date().toISOString(),
      },
    ]);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend || inputMessage).trim();
    if (!text || isLoading) return;

    const userMsg: ChatMessage = {
      id: 'user-' + Date.now(),
      sender: 'user',
      message: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputMessage('');
    setIsLoading(true);
    setQuotaWarning(null);

    try {
      const response = await apiService.sendChatMessage({
        message: text,
        session_id: sessionId,
      });

      const assistantMsg: ChatMessage = {
        id: 'assistant-' + Date.now(),
        sender: 'assistant',
        message: response.message,
        intent: response.intent,
        cached: response.cached,
        recommended_products: response.recommended_products,
        created_at: response.created_at || new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      if (onRefreshStats) onRefreshStats();
    } catch (err: any) {
      const isQuotaError =
        err.message?.includes('429') ||
        err.message?.includes('quota') ||
        err.message?.includes('RESOURCE_EXHAUSTED');

      if (isQuotaError) {
        setQuotaWarning(
          '⚠️ Hạn mức API đang tạm thời bận. Hệ thống đang tự động điều phối qua kênh dự phòng...'
        );
        // Tự động retry với fallback-heuristic
        try {
          const fallbackRes = await apiService.sendChatMessage({
            message: text,
            session_id: sessionId,
            model: 'fallback-heuristic',
          });

          const fallbackMsg: ChatMessage = {
            id: 'assistant-' + Date.now(),
            sender: 'assistant',
            message: `${fallbackRes.message}\n\n*(ℹ️ Trả lời qua Chế độ Đối Soát Trực Tiếp Lazada)*`,
            intent: fallbackRes.intent,
            cached: fallbackRes.cached,
            recommended_products: fallbackRes.recommended_products,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, fallbackMsg]);
          return;
        } catch {
          // ignore
        }
      }

      const errorMsg: ChatMessage = {
        id: 'err-' + Date.now(),
        sender: 'assistant',
        message: `⚠️ Không thể kết nối tới máy chủ API: ${err.message || 'Lỗi không xác định'}. Vui lòng kiểm tra lại dịch vụ backend.`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetSession = () => {
    const newSessionId = 'sess_' + Math.random().toString(36).substring(2, 11);
    setSessionId(newSessionId);
    setQuotaWarning(null);
    setMessages([
      {
        id: 'init-' + Date.now(),
        sender: 'assistant',
        message: '🔄 Đã làm mới phiên trò chuyện. Bạn muốn tìm sản phẩm nào tiếp theo?',
        created_at: new Date().toISOString(),
      },
    ]);
  };

  return (
    <div className="flex h-full w-full flex-col min-h-0 overflow-hidden rounded-2xl sm:rounded-3xl border border-slate-200 bg-white shadow-xl">
      {/* Chat Sub-Header */}
      <div className="shrink-0 flex flex-wrap items-center justify-between border-b border-slate-200 bg-slate-50/90 px-4 py-2.5 sm:py-3 gap-2 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs sm:text-sm font-bold text-slate-800">Trợ Lý AI Mua Sắm</span>
          </div>
        </div>

        <button
          onClick={handleResetSession}
          className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 shadow-2xs transition-colors hover:bg-slate-100 hover:text-slate-900 cursor-pointer"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Làm mới hội thoại</span>
        </button>
      </div>

      {/* Quota Exhausted Friendly Alert Banner */}
      {quotaWarning && (
        <div className="shrink-0 flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs font-medium text-amber-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-600" />
          <span>{quotaWarning}</span>
        </div>
      )}

      {/* Messages List Container - Internal Scroll Only */}
      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 space-y-4 sm:px-6 bg-slate-50/40">
        {messages.map((msg) => (
          <ChatMessageItem
            key={msg.id}
            message={msg}
            onViewProductHistory={onViewProductHistory}
          />
        ))}

        {isLoading && (
          <div className="flex items-start gap-3 chat-message-enter">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white shadow-md">
              <Bot className="h-5 w-5" />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3.5 text-sm text-slate-700 rounded-bl-none shadow-sm flex items-center gap-3">
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="text-slate-400 text-xs">Đang tìm kiếm và phân tích...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Suggestions & Input Box - Fixed at bottom of chat card */}
      <div className="shrink-0 border-t border-slate-200 bg-white p-3 sm:p-4 shadow-sm">
        <div className="mb-2.5">
          <QuickSuggestions onSelect={(prompt) => handleSendMessage(prompt)} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Nhập câu hỏi mua sắm (VD: 'mua điện thoại Pixel mới nhất', 'chuột gaming < 300k')..."
            className="flex-1 rounded-xl border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:bg-white focus:border-indigo-600 focus:outline-none focus:ring-2 focus:ring-indigo-600/20 shadow-2xs"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!inputMessage.trim() || isLoading}
            className="flex items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-2.5 text-sm font-bold text-white shadow-md shadow-indigo-600/20 transition-all hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <span>Gửi</span>
                <Send className="h-4 w-4" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

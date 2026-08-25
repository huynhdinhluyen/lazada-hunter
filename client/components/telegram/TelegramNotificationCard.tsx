'use client';

import React, { useState, useEffect } from 'react';
import { Send, Bell, CheckCircle2, AlertCircle, RefreshCw, ExternalLink, ShieldCheck, Zap } from 'lucide-react';
import { TelegramBotStatus } from '../../types';
import { apiService } from '../../services/api';

export const TelegramNotificationCard: React.FC = () => {
  const [status, setStatus] = useState<TelegramBotStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [customChatId, setCustomChatId] = useState('');
  const [isUpdatingChatId, setIsUpdatingChatId] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const fetchStatus = async () => {
    setIsLoading(true);
    try {
      const data = await apiService.getTelegramStatus();
      setStatus(data);
      if (data.chat_id) {
        setCustomChatId(data.chat_id);
      }
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message || 'Không thể tải trạng thái Telegram Bot' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSendTest = async () => {
    setIsTesting(true);
    setFeedback(null);
    try {
      const res = await apiService.sendTelegramTest(customChatId.trim() || undefined);
      setFeedback({ type: 'success', message: res.message || 'Đã gửi thông báo kiểm tra tới Telegram thành công!' });
    } catch (err: any) {
      setFeedback({
        type: 'error',
        message: err.message || 'Gửi thất bại. Hãy chắc chắn bạn đã mở Bot @lazamerce_alert_bot và bấm /start trên Telegram.',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveChatId = async () => {
    setIsUpdatingChatId(true);
    setFeedback(null);
    try {
      const res = await apiService.updateTelegramChatId(customChatId.trim() || undefined);
      setFeedback({ type: 'success', message: res.message });
      fetchStatus();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setIsUpdatingChatId(false);
    }
  };

  const isConnected = status?.is_connected;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-50 text-sky-600 border border-sky-200 shadow-2xs">
            <Send className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-slate-900">Trung Tâm Thông Báo Telegram</h3>
              {isConnected ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Đang hoạt động
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-bold text-rose-700 border border-rose-200">
                  Chưa kết nối
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">
              Nhận thông báo tức thì khi có deal giảm giá sâu và báo cáo tiến trình cào dữ liệu Lazada.
            </p>
          </div>
        </div>

        <button
          onClick={fetchStatus}
          disabled={isLoading}
          className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-100 hover:text-slate-900 transition-colors cursor-pointer shadow-2xs self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Làm mới trạng thái</span>
        </button>
      </div>

      {/* Alert Feedback */}
      {feedback && (
        <div
          className={`flex items-start gap-2.5 rounded-xl p-3 text-xs font-medium border ${
            feedback.type === 'success'
              ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
              : 'bg-rose-50 text-rose-900 border-rose-200'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600 mt-0.5" />
          ) : (
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          )}
          <span className="leading-relaxed">{feedback.message}</span>
        </div>
      )}

      {/* Main Bot Info Grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Card 1: Bot Identity */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            🤖 Telegram Bot
          </span>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-bold text-slate-900 text-sm">
                {status?.bot_info?.name || 'Lazada Alert Bot'}
              </div>
              <div className="text-xs font-mono text-sky-600 font-semibold">
                @{status?.bot_info?.username || 'lazamerce_alert_bot'}
              </div>
            </div>
            {status?.bot_info?.link && (
              <a
                href={status.bot_info.link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 rounded-lg bg-sky-600 px-2.5 py-1.5 text-xs font-bold text-white hover:bg-sky-700 transition-colors shadow-2xs"
              >
                <span>Mở Bot</span>
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>

        {/* Card 2: Configuration & Threshold */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            ⚙️ Cấu Hình Cảnh Báo
          </span>
          <div className="space-y-1.5 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Cảnh báo giảm giá sâu:</span>
              <span className="font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                Bật (Tự động)
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-600">Ngưỡng giảm giá kích hoạt:</span>
              <span className="font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                ≥ {status?.price_drop_threshold || 5.0}%
              </span>
            </div>
          </div>
        </div>

        {/* Card 3: Chat ID Setting */}
        <div className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 space-y-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
            🎯 Telegram Chat ID Nhận Tin
          </span>
          <div className="flex gap-2">
            <input
              type="text"
              value={customChatId}
              onChange={(e) => setCustomChatId(e.target.value)}
              placeholder="VD: 123456789 hoặc -100xxx"
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-mono text-slate-900 focus:border-sky-500 focus:outline-none"
            />
            <button
              onClick={handleSaveChatId}
              disabled={isUpdatingChatId}
              className="shrink-0 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 cursor-pointer"
            >
              {isUpdatingChatId ? 'Lưu...' : 'Lưu'}
            </button>
          </div>
        </div>
      </div>

      {/* Action Footer & Instruction */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between pt-2 border-t border-slate-100">
        <div className="flex items-start gap-2 text-xs text-slate-500">
          <ShieldCheck className="h-4 w-4 shrink-0 text-sky-600 mt-0.5" />
          <span>
            <strong>Hướng dẫn nhanh:</strong> Nhấp <strong>"Mở Bot"</strong> (hoặc tìm <code>@lazamerce_alert_bot</code>) trên Telegram, bấm <code>/start</code>, sau đó nhấn <strong>"Gửi Thông Báo Mẫu"</strong> bên cạnh để kiểm tra.
          </span>
        </div>

        <button
          onClick={handleSendTest}
          disabled={isTesting || !isConnected}
          className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-blue-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-sky-600/20 hover:from-sky-700 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-all"
        >
          {isTesting ? (
            <>
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              <span>Đang gửi qua Telegram...</span>
            </>
          ) : (
            <>
              <Zap className="h-3.5 w-3.5 fill-white" />
              <span>Gửi Thông Báo Mẫu Ngay</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

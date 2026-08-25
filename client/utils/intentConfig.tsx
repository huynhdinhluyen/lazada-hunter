import React from 'react';
import { Zap, ShieldCheck, Target, GitCompare, HelpCircle, AlertTriangle } from 'lucide-react';

export interface IntentBadgeConfig {
  icon: React.ReactNode;
  label: string;
  className: string;
}

export const getIntentBadgeConfig = (intent?: string | null, cached?: boolean): IntentBadgeConfig | null => {
  if (cached) {
    return {
      icon: <Zap className="h-3 w-3 fill-amber-500 text-amber-500" />,
      label: '⚡ Phản hồi siêu tốc (Đã có sẵn dữ liệu)',
      className: 'bg-amber-50 text-amber-700 border-amber-200',
    };
  }

  if (!intent) return null;

  switch (intent.toLowerCase()) {
    case 'safety_guard':
      return {
        icon: <ShieldCheck className="h-3 w-3" />,
        label: '🛡️ Quy chuẩn an toàn',
        className: 'bg-rose-50 text-rose-700 border-rose-200',
      };
    case 'chitchat_out_of_scope':
      return {
        icon: null,
        label: '💬 Trò chuyện & Hướng dẫn',
        className: 'bg-slate-100 text-slate-700 border-slate-200',
      };
    case 'clarification_needed':
      return {
        icon: <HelpCircle className="h-3 w-3" />,
        label: 'ℹ️ Cần làm rõ tiêu chí',
        className: 'bg-cyan-50 text-cyan-700 border-cyan-200',
      };
    case 'unrealistic_constraints':
      return {
        icon: <AlertTriangle className="h-3 w-3" />,
        label: '⚠️ Lưu ý về giá thị trường',
        className: 'bg-orange-50 text-orange-700 border-orange-200',
      };
    case 'comparison':
      return {
        icon: <GitCompare className="h-3 w-3" />,
        label: '⚖️ So sánh chi tiết sản phẩm',
        className: 'bg-violet-50 text-violet-700 border-violet-200',
      };
    case 'recommendation':
      return {
        icon: <Target className="h-3 w-3" />,
        label: '🎯 Gợi ý mua sắm tốt nhất',
        className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      };
    default:
      return {
        icon: null,
        label: intent,
        className: 'bg-slate-100 text-slate-700 border-slate-200',
      };
  }
};

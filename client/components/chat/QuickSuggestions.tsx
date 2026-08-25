'use client';

import React from 'react';
import { Sparkles, Phone, Mouse, Keyboard, Headphones, Laptop, Smartphone } from 'lucide-react';

interface QuickSuggestionsProps {
  onSelect: (prompt: string) => void;
}

export const QuickSuggestions: React.FC<QuickSuggestionsProps> = ({ onSelect }) => {
  const suggestions = [
    {
      label: 'Google Pixel mới nhất',
      prompt: 'giờ tôi muốn mua điện thoại Google Pixel mới nhất',
      icon: Phone,
      color: 'hover:border-indigo-400 hover:bg-indigo-50 text-indigo-700 bg-white border-slate-200',
    },
    {
      label: 'Chuột không dây < 300k',
      prompt: 'Tìm chuột không dây gaming dưới 300k',
      icon: Mouse,
      color: 'hover:border-emerald-400 hover:bg-emerald-50 text-emerald-700 bg-white border-slate-200',
    },
    {
      label: 'Tư vấn bàn phím cơ',
      prompt: 'Tư vấn cho mình bàn phím cơ',
      icon: Keyboard,
      color: 'hover:border-amber-400 hover:bg-amber-50 text-amber-700 bg-white border-slate-200',
    },
    {
      label: 'Tai nghe chống ồn < 1tr',
      prompt: 'Tư vấn tai nghe không dây chống ồn dưới 1 triệu',
      icon: Headphones,
      color: 'hover:border-sky-400 hover:bg-sky-50 text-sky-700 bg-white border-slate-200',
    },
    {
      label: 'MacBook Pro / Air',
      prompt: 'Tư vấn mua MacBook Pro hoặc MacBook Air giá tốt nhất',
      icon: Laptop,
      color: 'hover:border-purple-400 hover:bg-purple-50 text-purple-700 bg-white border-slate-200',
    },
    {
      label: 'iPhone chính hãng',
      prompt: 'Tìm điện thoại iPhone chính hãng VN/A giá ưu đãi nhất',
      icon: Smartphone,
      color: 'hover:border-rose-400 hover:bg-rose-50 text-rose-700 bg-white border-slate-200',
    },
  ];

  return (
    <div className="w-full">
      <div className="flex items-center gap-1.5 mb-1.5 text-xs font-bold text-slate-500">
        <Sparkles className="h-3.5 w-3.5 text-amber-500" />
        <span>Gợi ý câu hỏi kiểm thử nhanh:</span>
      </div>
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 sm:flex-wrap scrollbar-none">
        {suggestions.map((s, idx) => {
          const Icon = s.icon;
          return (
            <button
              key={idx}
              onClick={() => onSelect(s.prompt)}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium shadow-2xs transition-all duration-200 cursor-pointer whitespace-nowrap shrink-0 ${s.color}`}
            >
              <Icon className="h-3.5 w-3.5" />
              <span>{s.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

'use client';

import React from 'react';
import { Bot, User } from 'lucide-react';
import { ChatMessage, Product } from '../../types';
import { EmbeddedProductCard } from './EmbeddedProductCard';
import { MarkdownRenderer } from './MarkdownRenderer';
import { getIntentBadgeConfig } from '../../utils/intentConfig';
import { formatTimeOnly } from '../../utils/formatters';

interface ChatMessageItemProps {
  message: ChatMessage;
  onViewProductHistory?: (product: Product) => void;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onViewProductHistory,
}) => {
  const isUser = message.sender === 'user';
  const badgeConfig = !isUser ? getIntentBadgeConfig(message.intent, message.cached) : null;

  return (
    <div className={`flex w-full gap-3 ${isUser ? 'justify-end chat-message-user' : 'justify-start chat-message-enter'}`}>
      {!isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-600 text-white shadow-md shadow-indigo-600/20">
          <Bot className="h-5 w-5" />
        </div>
      )}

      <div className={`flex max-w-[88%] flex-col ${isUser ? 'items-end' : 'items-start'}`}>
        {badgeConfig && (
          <div className="mb-1.5 flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-bold border ${badgeConfig.className}`}>
              {badgeConfig.icon}
              {badgeConfig.label}
            </span>
          </div>
        )}

        <div
          className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${
            isUser
              ? 'bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-br-none'
              : 'border border-slate-200 bg-white text-slate-800 rounded-bl-none shadow-xs'
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.message}</p>
          ) : (
            <MarkdownRenderer content={message.message} />
          )}
        </div>

        {/* Embedded Products with rich images & clickable new tabs */}
        {!isUser && message.recommended_products && message.recommended_products.length > 0 && (
          <div className="mt-3.5 w-full">
            <div className="mb-2 text-xs font-bold text-slate-700">
              🛍️ Sản phẩm gợi ý phù hợp nhất ({message.recommended_products.length}):
            </div>
            <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
              {message.recommended_products.map((prod) => (
                <EmbeddedProductCard
                  key={prod.id}
                  product={prod}
                  onViewHistory={onViewProductHistory}
                />
              ))}
            </div>
          </div>
        )}

        <span className="mt-1 text-[10px] text-slate-400">
          {formatTimeOnly(message.created_at)}
        </span>
      </div>

      {isUser && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-100 text-indigo-800 border border-indigo-200">
          <User className="h-5 w-5" />
        </div>
      )}
    </div>
  );
};

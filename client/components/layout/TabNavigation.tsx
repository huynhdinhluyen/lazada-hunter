'use client';

import React from 'react';
import { MessageSquare, LayoutGrid, Send, Bookmark } from 'lucide-react';
import { useWatchlist } from '../../contexts/WatchlistContext';

export type TabId = 'chat' | 'catalog' | 'watchlist' | 'telegram';

interface TabNavigationProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  totalProducts?: number;
}

export const TabNavigation: React.FC<TabNavigationProps> = ({
  activeTab,
  onTabChange,
  totalProducts = 0,
}) => {
  const { savedCount } = useWatchlist();

  const tabs: {
    id: TabId;
    label: string;
    icon: any;
    badge?: string;
    badgeColor?: string;
    path: string;
  }[] = [
      {
        id: 'chat',
        label: 'AI Trợ Lý Mua Sắm',
        icon: MessageSquare,
        badge: '',
        badgeColor: 'bg-indigo-50 text-indigo-700 border-indigo-200',
        path: '/chat',
      },
      {
        id: 'catalog',
        label: 'Kho Sản Phẩm',
        icon: LayoutGrid,
        badge: totalProducts > 0 ? `${totalProducts} SP` : undefined,
        badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
        path: '/catalog',
      },
      {
        id: 'watchlist',
        label: 'Theo Dõi',
        icon: Bookmark,
        badge: savedCount > 0 ? `${savedCount}` : undefined,
        badgeColor: 'bg-violet-50 text-violet-700 border-violet-200',
        path: '/watchlist',
      },
      {
        id: 'telegram',
        label: 'Thông Báo Telegram',
        icon: Send,
        badge: 'Cảnh Báo Giảm Giá',
        badgeColor: 'bg-sky-50 text-sky-700 border-sky-200',
        path: '/telegram',
      },
    ];

  const handleTabClick = (tab: typeof tabs[0]) => {
    if (typeof window !== 'undefined') {
      window.history.pushState(null, '', tab.path);
    }
    onTabChange(tab.id);
  };

  return (
    <div className="w-full border-b border-slate-200 bg-white/95 backdrop-blur-md shadow-2xs sticky top-[57px] z-30">
      <div className="mx-auto flex max-w-7xl overflow-x-auto px-3 py-2 sm:px-6 gap-1 scrollbar-none">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => handleTabClick(tab)}
              className={`tab-nav-btn flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-bold transition-all duration-200 whitespace-nowrap cursor-pointer flex-shrink-0 sm:px-4 sm:py-2.5 ${isActive
                ? 'bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-indigo-500/10 backdrop-blur-xl border border-indigo-300/60 text-indigo-900 shadow-[0_4px_16px_rgba(99,102,241,0.12),inset_0_1px_2px_rgba(255,255,255,0.9)] ring-1 ring-indigo-500/15'
                : 'text-slate-600 hover:bg-slate-100/70 hover:text-slate-900 border border-transparent'
                }`}
            >
              <Icon className={`h-3.5 w-3.5 sm:h-4 sm:w-4 transition-colors ${isActive ? 'text-indigo-600' : 'text-slate-400'}`} />
              <span className="hidden sm:inline">{tab.label}</span>
              <span className="sm:hidden">{tab.label.split(' ')[0]}</span>

              {tab.badge && (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold border transition-all ${isActive
                    ? 'bg-indigo-100/80 text-indigo-800 border-indigo-200/80 shadow-2xs'
                    : tab.badgeColor
                    }`}
                >
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

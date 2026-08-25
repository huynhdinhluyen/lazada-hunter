'use client';

import { useState, useEffect } from 'react';
import { Header } from '../components/layout/Header';
import { TabNavigation, TabId } from '../components/layout/TabNavigation';
import { ChatInterface } from '../components/chat/ChatInterface';
import { ProductCatalog } from '../components/products/ProductCatalog';
import { WatchlistPanel } from '../components/products/WatchlistPanel';
import { TelegramNotificationCard } from '../components/telegram/TelegramNotificationCard';
import { PriceHistoryModal } from '../components/products/PriceHistoryModal';
import { AuthGuard } from '../components/auth/AuthGuard';
import { WatchlistProvider } from '../contexts/WatchlistContext';
import { Product } from '../types';
import { apiService } from '../services/api';

function HomeContent({ initialTab = 'chat' }: { initialTab?: TabId }) {
  const [activeTab, setActiveTab] = useState<TabId>(initialTab);
  const [serverOnline, setServerOnline] = useState<boolean>(true);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    const handlePopState = () => {
      const path = window.location.pathname;
      if (path.includes('/catalog')) setActiveTab('catalog');
      else if (path.includes('/watchlist')) setActiveTab('watchlist');
      else if (path.includes('/telegram')) setActiveTab('telegram');
      else if (path.includes('/chat')) setActiveTab('chat');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const checkStatus = async () => {
    try {
      await apiService.checkHealth();
      setServerOnline(true);
    } catch {
      setServerOnline(false);
    }
  };

  useEffect(() => {
    checkStatus();
  }, [activeTab]);

  return (
    <div className={`flex flex-col bg-slate-50 text-slate-900 ${activeTab === 'chat' ? 'h-screen overflow-hidden' : 'min-h-screen'}`}>
      {/* Top Header */}
      <Header />

      {/* Main Tab Navigation */}
      <TabNavigation
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab)}
      />

      {/* Main Container */}
      <main className={`mx-auto w-full max-w-7xl flex-1 px-3 sm:px-6 ${activeTab === 'chat' ? 'min-h-0 py-2 sm:py-3.5 flex flex-col overflow-hidden' : 'py-5 sm:py-6'}`}>
        {/* Tab 1: AI Shopping Assistant */}
        {activeTab === 'chat' && (
          <div className="h-full w-full min-h-0 flex flex-col animate-fadeIn">
            <ChatInterface
              onViewProductHistory={(prod) => setSelectedProduct(prod)}
              onRefreshStats={checkStatus}
            />
          </div>
        )}

        {/* Tab 2: Product Catalog & Prices */}
        {activeTab === 'catalog' && (
          <div className="animate-fadeIn">
            <ProductCatalog />
          </div>
        )}

        {/* Tab 3: Watchlist */}
        {activeTab === 'watchlist' && (
          <div className="animate-fadeIn">
            <WatchlistPanel onViewHistory={(prod) => setSelectedProduct(prod)} />
          </div>
        )}

        {/* Tab 4: Telegram Notification Center */}
        {activeTab === 'telegram' && (
          <div className="animate-fadeIn">
            <TelegramNotificationCard />
          </div>
        )}
      </main>

      {/* Price History Modal */}
      <PriceHistoryModal
        product={selectedProduct}
        onClose={() => setSelectedProduct(null)}
      />

      {/* Footer (Only for scrollable tabs) */}
      {activeTab !== 'chat' && (
        <footer className="border-t border-slate-200/80 bg-white/80 backdrop-blur-sm py-4 text-center text-xs text-slate-400">
          <div className="mx-auto max-w-7xl px-4 sm:px-6">
            Lazada Hunter &copy; {new Date().getFullYear()} &nbsp;·&nbsp; Powered by FastAPI, PostgreSQL, Qdrant Cloud, NVIDIA Llama 3.1 &amp; Next.js 16
          </div>
        </footer>
      )}
    </div>
  );
}

export default function Home({ initialTab = 'chat' }: { initialTab?: TabId }) {
  return (
    <AuthGuard>
      <WatchlistProvider>
        <HomeContent initialTab={initialTab} />
      </WatchlistProvider>
    </AuthGuard>
  );
}

'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useSession } from 'next-auth/react';
import { Product } from '../types';
import { apiService } from '../services/api';

interface WatchlistItem {
  id: number;
  product_id: number;
  user_id: string;
  note?: string;
  created_at: string;
  product: Product;
}

interface WatchlistContextType {
  savedItems: WatchlistItem[];
  savedCount: number;
  isSaved: (productId: number) => boolean;
  saveProduct: (product: Product) => Promise<void>;
  removeProduct: (productId: number) => Promise<void>;
  isLoading: boolean;
  refresh: () => Promise<void>;
}

const WatchlistContext = createContext<WatchlistContextType>({
  savedItems: [],
  savedCount: 0,
  isSaved: () => false,
  saveProduct: async () => {},
  removeProduct: async () => {},
  isLoading: false,
  refresh: async () => {},
});

export const useWatchlist = () => useContext(WatchlistContext);

export const WatchlistProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: session } = useSession();
  const [savedItems, setSavedItems] = useState<WatchlistItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const userId = session?.user?.email || '';

  const refresh = useCallback(async () => {
    if (!userId) return;
    setIsLoading(true);
    try {
      const data = await apiService.getWatchlist(userId);
      setSavedItems(data.items || []);
    } catch (err) {
      console.error('Lỗi tải watchlist:', err);
    } finally {
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (userId) {
      refresh();
    } else {
      setSavedItems([]);
    }
  }, [userId, refresh]);

  const isSaved = (productId: number): boolean => {
    return savedItems.some(item => item.product_id === productId);
  };

  const saveProduct = async (product: Product): Promise<void> => {
    if (!userId) return;
    try {
      await apiService.addToWatchlist(userId, product.id);
      // Optimistic update
      setSavedItems(prev => [
        {
          id: Date.now(),
          product_id: product.id,
          user_id: userId,
          created_at: new Date().toISOString(),
          product,
        } as WatchlistItem,
        ...prev,
      ]);
    } catch (err) {
      console.error('Lỗi lưu sản phẩm:', err);
      await refresh();
    }
  };

  const removeProduct = async (productId: number): Promise<void> => {
    if (!userId) return;
    try {
      // Optimistic update
      setSavedItems(prev => prev.filter(item => item.product_id !== productId));
      await apiService.removeFromWatchlist(userId, productId);
    } catch (err) {
      console.error('Lỗi xóa sản phẩm:', err);
      await refresh();
    }
  };

  return (
    <WatchlistContext.Provider value={{
      savedItems,
      savedCount: savedItems.length,
      isSaved,
      saveProduct,
      removeProduct,
      isLoading,
      refresh,
    }}>
      {children}
    </WatchlistContext.Provider>
  );
};

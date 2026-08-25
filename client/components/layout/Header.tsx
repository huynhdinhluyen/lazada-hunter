'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ShoppingBag, Sparkles, LogOut, User, ChevronDown } from 'lucide-react';
import { useSession, signOut } from 'next-auth/react';
import Image from 'next/image';

interface HeaderProps {
  serverOnline?: boolean;
}

export const Header: React.FC<HeaderProps> = () => {
  const { data: session } = useSession();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-200/80 bg-white/90 backdrop-blur-xl shadow-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5 sm:px-6">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-violet-600 shadow-md shadow-indigo-500/25 sm:h-10 sm:w-10">
            <ShoppingBag className="h-4.5 w-4.5 text-white sm:h-5 sm:w-5" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-black tracking-tight text-slate-900 sm:text-lg">
                Lazada Hunter
              </h1>
              <span className="hidden sm:inline-flex items-center gap-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 border border-blue-200">
                <Sparkles className="h-3 w-3 text-blue-600" />
                AI-Powered
              </span>
            </div>
            <p className="hidden text-[11px] text-slate-400 sm:block">
              Lazada · AI Shopping Advisor
            </p>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* User Avatar & Dropdown */}
          {session?.user && (
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setShowDropdown(!showDropdown)}
                className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs transition-all hover:bg-slate-100 hover:border-slate-300 cursor-pointer"
                id="user-menu-btn"
              >
                {session.user.image ? (
                  <Image
                    src={session.user.image}
                    alt={session.user.name || 'Avatar'}
                    width={28}
                    height={28}
                    className="rounded-full ring-2 ring-indigo-100"
                  />
                ) : (
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
                    <User className="h-3.5 w-3.5" />
                  </div>
                )}
                <span className="hidden font-semibold text-slate-800 sm:block max-w-[120px] truncate">
                  {session.user.name}
                </span>
                <ChevronDown className={`h-3.5 w-3.5 text-slate-500 transition-transform ${showDropdown ? 'rotate-180' : ''}`} />
              </button>

              {/* Dropdown */}
              {showDropdown && (
                <div className="absolute right-0 top-full mt-2 w-56 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl shadow-slate-900/10 z-50 animate-fadeIn">
                  <div className="border-b border-slate-100 px-3 pb-2.5 pt-1.5 mb-1">
                    <p className="text-xs font-bold text-slate-900 truncate">{session.user.name}</p>
                    <p className="text-[11px] text-slate-500 truncate">{session.user.email}</p>
                  </div>
                  <button
                    onClick={() => signOut({ callbackUrl: '/login' })}
                    className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold text-rose-600 transition-colors hover:bg-rose-50 cursor-pointer"
                    id="logout-btn"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                    <span>Đăng xuất</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

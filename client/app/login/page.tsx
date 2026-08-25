'use client';

import React, { useState, useEffect } from 'react';
import { signIn } from 'next-auth/react';
import { ShoppingBag, Sparkles, Shield, Zap, TrendingDown, Bell } from 'lucide-react';

export default function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleGoogleLogin = async () => {
    setIsLoading(true);
    try {
      await signIn('google', { callbackUrl: '/' });
    } catch {
      setIsLoading(false);
    }
  };

  const features = [
    {
      icon: <Sparkles className="h-5 w-5 text-indigo-400" />,
      title: 'AI Tư Vấn Thông Minh',
      desc: 'Trợ Lý tìm deal tốt nhất cho bạn'
    },
    {
      icon: <TrendingDown className="h-5 w-5 text-emerald-400" />,
      title: 'Theo Dõi Biến Động Giá',
      desc: 'Biểu đồ giá realtime, cảnh báo ngay khi giảm sâu'
    },
    {
      icon: <Bell className="h-5 w-5 text-amber-400" />,
      title: 'Thông Báo Telegram',
      desc: 'Nhận alert tức thì ngay khi có deal hot từ Lazada'
    },
    {
      icon: <Shield className="h-5 w-5 text-rose-400" />,
      title: 'Danh Sách Theo Dõi',
      desc: 'Lưu sản phẩm yêu thích, theo dõi giá cá nhân hóa'
    },
  ];

  return (
    <div className="login-page min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Animated background gradient */}
      <div className="login-bg-gradient" />
      <div className="login-bg-orb login-bg-orb-1" />
      <div className="login-bg-orb login-bg-orb-2" />
      <div className="login-bg-orb login-bg-orb-3" />

      {/* Grid pattern overlay */}
      <div className="login-grid-overlay" />

      {/* Main card */}
      <div className={`login-card relative z-10 w-full max-w-md mx-4 transition-all duration-700 ${mounted ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'}`}>
        {/* Logo + Title */}
        <div className="text-center mb-8">
          <div className="login-logo-wrap mx-auto mb-5">
            <div className="login-logo-inner">
              <ShoppingBag className="h-9 w-9 text-white" />
            </div>
            <div className="login-logo-ping" />
          </div>

          <h1 className="text-3xl font-black text-white mb-2 tracking-tight">
            Lazada Hunter
          </h1>
          <p className="text-slate-400 text-sm leading-relaxed">
            Trợ lý mua sắm thông minh
          </p>
        </div>

        {/* Feature list */}
        <div className="grid grid-cols-2 gap-3 mb-8">
          {features.map((f, i) => (
            <div
              key={i}
              className="login-feature-card"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="mb-2">{f.icon}</div>
              <div className="text-xs font-bold text-white mb-1">{f.title}</div>
              <div className="text-[11px] text-slate-400 leading-relaxed">{f.desc}</div>
            </div>
          ))}
        </div>

        {/* Google Sign In Button */}
        <button
          id="google-signin-btn"
          onClick={handleGoogleLogin}
          disabled={isLoading}
          className="login-google-btn"
        >
          {isLoading ? (
            <div className="login-spinner" />
          ) : (
            <svg className="h-5 w-5 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
            </svg>
          )}
          <span className="font-bold">
            {isLoading ? 'Đang đăng nhập...' : 'Tiếp tục với Google'}
          </span>
          {!isLoading && <Zap className="h-4 w-4 text-indigo-400 shrink-0" />}
        </button>

        {/* Footer note */}
        <p className="text-center text-[11px] text-slate-500 mt-5 leading-relaxed">
          Bằng cách đăng nhập, bạn đồng ý với điều khoản sử dụng.
          <br />
          Thông tin của bạn được bảo mật tuyệt đối.
        </p>
      </div>
    </div>
  );
}

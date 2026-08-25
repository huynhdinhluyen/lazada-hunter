import type { Metadata } from 'next';
import { SessionProvider } from 'next-auth/react';
import './globals.css';

export const metadata: Metadata = {
  title: 'Lazada Hunter — AI-Powered Shopping Assistant',
  description: 'Trợ lý mua sắm thông minh: Theo dõi giá Lazada, tư vấn AI, cảnh báo deal giảm giá và thông báo Telegram tức thì.',
  keywords: ['Lazada', 'AI Shopping', 'Price Tracker', 'Deal Hunter', 'Vietnam'],
  openGraph: {
    title: 'Lazada Hunter — AI-Powered Shopping Assistant',
    description: 'Trợ lý mua sắm thông minh Lazada Việt Nam',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="antialiased scroll-smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <SessionProvider>
          {children}
        </SessionProvider>
      </body>
    </html>
  );
}

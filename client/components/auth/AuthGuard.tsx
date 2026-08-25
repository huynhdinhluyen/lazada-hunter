'use client';

import React, { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

interface AuthGuardProps {
  children: React.ReactNode;
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [isRedirecting, setIsRedirecting] = useState(false);

  useEffect(() => {
    if (status === 'unauthenticated' && !isRedirecting) {
      setIsRedirecting(true);
      router.push('/login');
    }
  }, [status, isRedirecting, router]);

  if (status === 'loading' || isRedirecting) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <div className="auth-loading-logo">
            <Loader2 className="h-8 w-8 text-indigo-400 animate-spin" />
          </div>
          <div className="text-center">
            <p className="text-slate-300 font-semibold text-sm">Đang xác thực...</p>
            <p className="text-slate-500 text-xs mt-1">Lazada Hunter đang khởi tạo phiên làm việc</p>
          </div>
        </div>
      </div>
    );
  }

  if (!session) {
    return null;
  }

  return <>{children}</>;
};

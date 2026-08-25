import React, { useState } from 'react';
import { Package } from 'lucide-react';

interface ProductImageThumbnailProps {
  src?: string | null;
  alt: string;
  className?: string;
  fallbackText?: string;
}

export const ProductImageThumbnail: React.FC<ProductImageThumbnailProps> = ({
  src,
  alt,
  className = 'h-full w-full object-contain p-2',
  fallbackText = 'Sản phẩm Lazada',
}) => {
  const [error, setError] = useState(false);

  let cleanSrc = src ? src.trim() : '';
  if (cleanSrc.startsWith('//')) {
    cleanSrc = `https:${cleanSrc}`;
  }

  if (!cleanSrc || error) {
    return (
      <div className="flex h-full w-full flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 p-2 text-slate-400">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-white shadow-2xs mb-1">
          <Package className="h-4 w-4 text-indigo-400" />
        </div>
        <span className="text-[10px] font-medium text-slate-500 line-clamp-1 text-center px-1">
          {alt || fallbackText}
        </span>
      </div>
    );
  }

  return (
    <img
      src={cleanSrc}
      alt={alt}
      className={`${className} transition-transform duration-300 group-hover:scale-105`}
      onError={() => setError(true)}
      loading="lazy"
      crossOrigin="anonymous"
    />
  );
};

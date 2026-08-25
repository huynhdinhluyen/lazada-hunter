/**
 * Utilities dùng chung để định dạng tiền tệ, số liệu và ngày tháng (DRY)
 */

export const formatPrice = (price: number | null | undefined): string => {
  if (price === null || price === undefined || isNaN(price)) return '0 ₫';
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    maximumFractionDigits: 0,
  }).format(price);
};

export const formatCurrency = formatPrice;

export const formatNumber = (num: number | null | undefined): string => {
  if (num === null || num === undefined || isNaN(num)) return '0';
  return num.toLocaleString('vi-VN');
};

export const formatDateTime = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleString('vi-VN');
  } catch {
    return dateStr;
  }
};

export const formatTimeOnly = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '';
  try {
    return new Date(dateStr).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
};

export const formatDiscount = (percent: number | null | undefined): string | null => {
  if (!percent || percent <= 0) return null;
  return `-${Math.round(percent)}%`;
};

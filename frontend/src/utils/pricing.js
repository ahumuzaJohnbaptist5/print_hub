/** Pricing logic matching backend/orders/models.py Order.calculate_price() */
export const BASE_PRICE_BW = 200;
export const COLOR_SURCHARGE = 100;

export function calculatePrice(pageCount, isColor, isDoubleSided) {
  const pages = Math.max(1, parseInt(pageCount) || 1);
  const pricePerPage = isColor ? BASE_PRICE_BW + COLOR_SURCHARGE : BASE_PRICE_BW;
  const effectivePages = isDoubleSided ? Math.ceil(pages / 2) : pages;
  const total = pricePerPage * effectivePages;
  return { pages, pricePerPage, effectivePages, total };
}

export function formatUgx(amount) {
  return `UGX ${amount.toLocaleString('en-US')}`;
}

export const ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.png', '.jpg', '.jpeg'];
export const MAX_UPLOAD_SIZE = 10 * 1024 * 1024;

export function validateFile(file) {
  if (!file) return null;
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(ext)) return 'Invalid file type.';
  if (file.size > MAX_UPLOAD_SIZE) return 'File exceeds 10MB limit.';
  return null;
}

export function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

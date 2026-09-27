import React from 'react';
import {
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from 'lucide-react';

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  pageSizeOptions?: number[];
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  itemName?: string;
  className?: string;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  pageSizeOptions = [12, 24, 48],
  onPageChange,
  onPageSizeChange,
  itemName = 'items',
  className = '',
}) => {
  if (totalItems === 0) return null;

  const validCurrentPage = Math.min(Math.max(1, currentPage), Math.max(1, totalPages));
  const startItem = totalItems === 0 ? 0 : (validCurrentPage - 1) * pageSize + 1;
  const endItem = Math.min(validCurrentPage * pageSize, totalItems);

  // Generate visible page numbers with smart ellipsis
  const getPageNumbers = (): (number | 'ellipsis')[] => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    const pages: (number | 'ellipsis')[] = [];
    pages.push(1);

    if (validCurrentPage > 3) {
      pages.push('ellipsis');
    }

    const start = Math.max(2, validCurrentPage - 1);
    const end = Math.min(totalPages - 1, validCurrentPage + 1);

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (validCurrentPage < totalPages - 2) {
      pages.push('ellipsis');
    }

    pages.push(totalPages);
    return pages;
  };

  const pages = getPageNumbers();

  return (
    <div
      className={`flex flex-col sm:flex-row items-center justify-between gap-3 px-3 py-2.5 bg-[#383330] border border-[#3f3a36] rounded-[4px] text-xs ${className}`}
      aria-label="Pagination Navigation"
    >
      {/* Item Range Summary */}
      <div className="text-[#aea69c] font-mono text-[11px] sm:text-xs">
        Showing <span className="text-[#f7f5f0] font-medium">{startItem}</span>–
        <span className="text-[#f7f5f0] font-medium">{endItem}</span> of{' '}
        <span className="text-[#f7f5f0] font-medium">{totalItems}</span> {itemName}
      </div>

      {/* Navigation Controls */}
      <div className="flex items-center gap-1.5 flex-wrap justify-center">
        {/* First Page */}
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={validCurrentPage <= 1}
          aria-label="First page"
          title="First page"
          className="p-1 rounded-[3px] border border-[#3f3a36] bg-[#2b2622] text-[#c9c0ad] hover:text-[#f7f5f0] hover:border-[#544d47] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
        >
          <ChevronsLeft className="w-3.5 h-3.5" />
        </button>

        {/* Previous Page */}
        <button
          type="button"
          onClick={() => onPageChange(validCurrentPage - 1)}
          disabled={validCurrentPage <= 1}
          aria-label="Previous page"
          title="Previous page"
          className="p-1 rounded-[3px] border border-[#3f3a36] bg-[#2b2622] text-[#c9c0ad] hover:text-[#f7f5f0] hover:border-[#544d47] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>

        {/* Numbered Pages (Desktop/Tablet) */}
        <div className="hidden sm:flex items-center gap-1">
          {pages.map((p, idx) => {
            if (p === 'ellipsis') {
              return (
                <span
                  key={`ellipsis-${idx}`}
                  className="px-1.5 py-0.5 text-[#aea69c] font-mono text-xs select-none"
                >
                  …
                </span>
              );
            }

            const isActive = p === validCurrentPage;
            return (
              <button
                key={p}
                type="button"
                onClick={() => onPageChange(p)}
                aria-label={`Page ${p}`}
                aria-current={isActive ? 'page' : undefined}
                className={`min-w-[28px] h-7 px-1.5 flex items-center justify-center rounded-[3px] font-mono text-xs transition-colors cursor-pointer ${
                  isActive
                    ? 'bg-[#f7f5f0] text-[#2b2622] font-semibold border border-[#f7f5f0]'
                    : 'bg-[#2b2622] text-[#dad2c1] border border-[#3f3a36] hover:border-[#544d47] hover:text-[#f7f5f0]'
                }`}
              >
                {p}
              </button>
            );
          })}
        </div>

        {/* Mobile Compact Page Indicator */}
        <span className="sm:hidden font-mono text-[11px] px-2 text-[#dad2c1]">
          {validCurrentPage} / {totalPages}
        </span>

        {/* Next Page */}
        <button
          type="button"
          onClick={() => onPageChange(validCurrentPage + 1)}
          disabled={validCurrentPage >= totalPages}
          aria-label="Next page"
          title="Next page"
          className="p-1 rounded-[3px] border border-[#3f3a36] bg-[#2b2622] text-[#c9c0ad] hover:text-[#f7f5f0] hover:border-[#544d47] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>

        {/* Last Page */}
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={validCurrentPage >= totalPages}
          aria-label="Last page"
          title="Last page"
          className="p-1 rounded-[3px] border border-[#3f3a36] bg-[#2b2622] text-[#c9c0ad] hover:text-[#f7f5f0] hover:border-[#544d47] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
        >
          <ChevronsRight className="w-3.5 h-3.5" />
        </button>

        {/* Items Per Page Selector */}
        {onPageSizeChange && pageSizeOptions && pageSizeOptions.length > 1 && (
          <div className="ml-2 pl-2 border-l border-[#3f3a36] flex items-center gap-1.5">
            <select
              value={pageSize}
              onChange={(e) => onPageSizeChange(Number(e.target.value))}
              aria-label={`Select ${itemName} per page`}
              className="bg-[#2b2622] border border-[#3f3a36] rounded-[3px] px-1.5 py-1 text-[11px] font-mono text-[#f7f5f0] focus:outline-none focus:border-[#dad2c1] cursor-pointer"
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt} className="bg-[#2b2622] text-[#f7f5f0]">
                  {opt} / page
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
    </div>
  );
};

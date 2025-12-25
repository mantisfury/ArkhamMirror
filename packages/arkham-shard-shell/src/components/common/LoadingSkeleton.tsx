/**
 * LoadingSkeleton - Loading placeholder for shard content
 */

// Generic loading skeleton - can be used anywhere
export function LoadingSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`ach-loading ${className}`}>
      <span className="spin">Loading...</span>
    </div>
  );
}

export function ShardLoadingSkeleton() {
  return (
    <div className="shard-loading">
      <div className="skeleton-header">
        <div className="skeleton skeleton-icon" />
        <div className="skeleton-text">
          <div className="skeleton skeleton-title" />
          <div className="skeleton skeleton-subtitle" />
        </div>
      </div>
      <div className="skeleton-content">
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line" />
        <div className="skeleton skeleton-line short" />
      </div>
      <div className="skeleton-table">
        <div className="skeleton skeleton-row" />
        <div className="skeleton skeleton-row" />
        <div className="skeleton skeleton-row" />
        <div className="skeleton skeleton-row" />
      </div>
    </div>
  );
}

export function TableSkeleton({ columns = 4, rows = 5 }: { columns?: number; rows?: number }) {
  return (
    <div className="table-skeleton">
      <div className="skeleton-table-header">
        {Array.from({ length: columns }).map((_, i) => (
          <div key={i} className="skeleton skeleton-header-cell" />
        ))}
      </div>
      <div className="skeleton-table-body">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="skeleton-table-row">
            {Array.from({ length: columns }).map((_, colIndex) => (
              <div key={colIndex} className="skeleton skeleton-cell" />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

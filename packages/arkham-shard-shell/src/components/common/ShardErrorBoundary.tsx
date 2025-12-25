/**
 * ShardErrorBoundary - Error isolation for shard content
 *
 * Catches errors within a shard and displays fallback UI
 * without crashing the entire shell.
 */

import { ErrorBoundary, FallbackProps } from 'react-error-boundary';
import { ReactNode, useEffect } from 'react';
import { useToast } from '../../context/ToastContext';
import { Icon } from './Icon';

interface ShardErrorBoundaryProps {
  children: ReactNode;
  shardName: string;
}

function ShardErrorFallback({ error, resetErrorBoundary, shardName }: FallbackProps & { shardName: string }) {
  const { toast } = useToast();

  useEffect(() => {
    toast.error(`Error in ${shardName}: ${error.message}`);
  }, [error, shardName, toast]);

  return (
    <div className="shard-error">
      <div className="shard-error-content">
        <Icon name="AlertTriangle" size={48} className="error-icon" />
        <h2>Something went wrong in {shardName}</h2>
        <p className="error-message">{error.message}</p>
        <div className="error-actions">
          <button className="btn btn-primary" onClick={resetErrorBoundary}>
            <Icon name="RefreshCw" size={16} />
            Try Again
          </button>
          <button className="btn btn-secondary" onClick={() => window.location.href = '/'}>
            <Icon name="Home" size={16} />
            Go to Dashboard
          </button>
        </div>
        {process.env.NODE_ENV === 'development' && (
          <details className="error-details">
            <summary>Error Details</summary>
            <pre>{error.stack}</pre>
          </details>
        )}
      </div>
    </div>
  );
}

export function ShardErrorBoundary({ children, shardName }: ShardErrorBoundaryProps) {
  return (
    <ErrorBoundary
      FallbackComponent={(props) => <ShardErrorFallback {...props} shardName={shardName} />}
      onReset={() => {
        // Reset any state that might have caused the error
        window.location.reload();
      }}
    >
      {children}
    </ErrorBoundary>
  );
}

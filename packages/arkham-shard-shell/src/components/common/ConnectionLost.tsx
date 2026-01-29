/**
 * ConnectionLost - Full-page overlay when Frame is unreachable
 */

import { useState, useEffect } from 'react';
import { Icon } from './Icon';
import { apiFetch } from '../../utils/api';

interface ConnectionLostProps {
  lastConnectedTime?: Date;
}

export function ConnectionLost({ lastConnectedTime }: ConnectionLostProps) {
  const [retryCount, setRetryCount] = useState(0);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    // Auto-retry every 5 seconds
    const interval = setInterval(async () => {
      setRetrying(true);
      try {
        const response = await apiFetch('/api/health');
        if (response.ok) {
          window.location.reload();
        }
      } catch {
        setRetryCount(c => c + 1);
      } finally {
        setRetrying(false);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString();
  };

  return (
    <div className="connection-lost-overlay">
      <div className="connection-lost-content">
        <Icon name="WifiOff" size={64} className="connection-icon" />
        <h1>Connection Lost</h1>
        <p>Unable to connect to the server. Retrying automatically...</p>
        {lastConnectedTime && (
          <p className="last-connected">
            Last connected: {formatTime(lastConnectedTime)}
          </p>
        )}
        <div className="retry-status">
          {retrying ? (
            <>
              <Icon name="Loader2" size={16} className="spinning" />
              <span>Attempting to reconnect...</span>
            </>
          ) : (
            <span>Retry attempt #{retryCount + 1} in 5 seconds</span>
          )}
        </div>
        <button
          className="btn btn-primary"
          onClick={() => window.location.reload()}
          disabled={retrying}
        >
          <Icon name="RefreshCw" size={16} />
          Retry Now
        </button>
      </div>
    </div>
  );
}

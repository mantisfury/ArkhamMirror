/**
 * ContentArea - Main content area for shard rendering
 *
 * Wraps content with error boundary and suspense
 */

import { Suspense, ReactNode } from 'react';
import { ShardErrorBoundary } from '../common/ShardErrorBoundary';
import { ShardLoadingSkeleton } from '../common/LoadingSkeleton';
import { useShell } from '../../context/ShellContext';

interface ContentAreaProps {
  children: ReactNode;
}

export function ContentArea({ children }: ContentAreaProps) {
  const { currentShard } = useShell();
  const shardName = currentShard?.name || 'unknown';

  return (
    <main className="content-area">
      <ShardErrorBoundary shardName={shardName}>
        <Suspense fallback={<ShardLoadingSkeleton />}>
          {children}
        </Suspense>
      </ShardErrorBoundary>
    </main>
  );
}

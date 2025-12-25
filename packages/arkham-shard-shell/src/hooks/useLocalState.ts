/**
 * useLocalState - localStorage persistence with shard prefix
 *
 * Storage format: {shardName}:{key} = JSON.stringify(value)
 */

import { useState, useEffect, useCallback } from 'react';

export function useLocalState<T>(
  shardName: string,
  key: string,
  defaultValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  const storageKey = `${shardName}:${key}`;

  const [state, setState] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored !== null) {
        return JSON.parse(stored);
      }
    } catch {
      // Invalid JSON, use default
    }
    return defaultValue;
  });

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch (error) {
      console.warn(`Failed to persist ${storageKey}:`, error);
    }
  }, [state, storageKey]);

  const setLocalState = useCallback((value: T | ((prev: T) => T)) => {
    setState(prev => {
      const next = typeof value === 'function' ? (value as (prev: T) => T)(prev) : value;
      return next;
    });
  }, []);

  return [state, setLocalState];
}

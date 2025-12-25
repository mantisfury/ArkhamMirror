/**
 * useUrlParams - Flat URL state management
 *
 * Rules (from UI_SHELL_PLAN_v5):
 * - Type coercion from defaults (number default = parse as number)
 * - Default values omitted from URL (except booleans)
 * - No JSON blobs - each param is flat key-value
 * - Booleans: true = "true", false = "false" (explicit, supports default: true)
 */

import { useSearchParams } from 'react-router-dom';
import { useCallback, useMemo } from 'react';

type ParamValue = string | number | boolean | null;
type ParamDefaults<T extends Record<string, ParamValue>> = T;

export function useUrlParams<T extends Record<string, ParamValue>>(
  defaults: ParamDefaults<T>
): [T, (updates: Partial<T>) => void, (key: keyof T) => void] {
  const [searchParams, setSearchParams] = useSearchParams();

  const params = useMemo(() => {
    const result = { ...defaults } as T;

    for (const key of Object.keys(defaults) as (keyof T)[]) {
      const urlValue = searchParams.get(key as string);
      if (urlValue === null) continue;

      const defaultValue = defaults[key];

      if (typeof defaultValue === 'number') {
        const parsed = Number(urlValue);
        if (!isNaN(parsed)) {
          result[key] = parsed as T[keyof T];
        }
      } else if (typeof defaultValue === 'boolean') {
        // v5.1: Booleans are explicit - "true" or "false"
        result[key] = (urlValue === 'true') as T[keyof T];
      } else {
        result[key] = urlValue as T[keyof T];
      }
    }

    return result;
  }, [searchParams, defaults]);

  const setParams = useCallback((updates: Partial<T>) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);

      for (const [key, value] of Object.entries(updates)) {
        const defaultValue = defaults[key as keyof T];

        if (value === null || value === undefined) {
          next.delete(key);
        } else if (typeof value === 'boolean') {
          // v5.1: Booleans are ALWAYS explicit (true/false), never omitted
          // This supports filters with default: true
          next.set(key, String(value));
        } else if (value === defaultValue) {
          // Non-boolean defaults are omitted to keep URLs clean
          next.delete(key);
        } else {
          next.set(key, String(value));
        }
      }

      return next;
    }, { replace: true });
  }, [defaults, setSearchParams]);

  const clearParam = useCallback((key: keyof T) => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.delete(key as string);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  return [params, setParams, clearParam];
}

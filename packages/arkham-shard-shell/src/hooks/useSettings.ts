/**
 * useSettings - Hook for reading application settings
 *
 * Fetches settings from the settings API and provides typed access.
 * Includes caching to avoid redundant API calls.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

interface Setting {
  key: string;
  value: unknown;
  default_value: unknown;
  category: string;
  data_type: string;
  label: string;
  description: string;
}

interface SettingsCache {
  data: Map<string, unknown>;
  timestamp: number;
}

// Simple cache shared across hook instances
let settingsCache: SettingsCache | null = null;
const CACHE_TTL = 60000; // 1 minute cache

interface UseSettingsResult {
  /** Get a setting value with type casting */
  getSetting: <T>(key: string, defaultValue: T) => T;
  /** All settings loaded */
  settings: Map<string, unknown>;
  /** Loading state */
  loading: boolean;
  /** Error if fetch failed */
  error: Error | null;
  /** Force refresh settings from API */
  refresh: () => void;
}

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<Map<string, unknown>>(
    settingsCache?.data ?? new Map()
  );
  const [loading, setLoading] = useState(!settingsCache);
  const [error, setError] = useState<Error | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchSettings = useCallback(async (force = false) => {
    // Use cache if valid and not forcing refresh
    if (!force && settingsCache && Date.now() - settingsCache.timestamp < CACHE_TTL) {
      setSettings(settingsCache.data);
      setLoading(false);
      return;
    }

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/settings/', {
        signal: abortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      const settingsMap = new Map<string, unknown>();

      // Handle paginated response or direct array
      const items: Setting[] = result.items || result;
      items.forEach((setting: Setting) => {
        settingsMap.set(setting.key, setting.value);
      });

      // Update cache
      settingsCache = {
        data: settingsMap,
        timestamp: Date.now(),
      };

      setSettings(settingsMap);
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }
      setError(err instanceof Error ? err : new Error('Failed to load settings'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
    return () => abortRef.current?.abort();
  }, [fetchSettings]);

  const getSetting = useCallback(<T,>(key: string, defaultValue: T): T => {
    const value = settings.get(key);
    if (value === undefined) {
      return defaultValue;
    }
    return value as T;
  }, [settings]);

  const refresh = useCallback(() => {
    fetchSettings(true);
  }, [fetchSettings]);

  return { getSetting, settings, loading, error, refresh };
}

// Convenience hooks for specific settings
export function usePageSize(): number {
  const { getSetting } = useSettings();
  return getSetting('performance.page_size', 20);
}

export function useReduceMotion(): boolean {
  const { getSetting } = useSettings();
  return getSetting('performance.reduce_motion', false);
}

export function useTableVirtualization(): boolean {
  const { getSetting } = useSettings();
  return getSetting('performance.table_virtualization', true);
}

export function useApiTimeout(): number {
  const { getSetting } = useSettings();
  return getSetting('advanced.api_timeout', 30) * 1000; // Convert to ms
}

export function useMaxUploadSize(): number {
  const { getSetting } = useSettings();
  return getSetting('storage.max_file_size_mb', 100);
}

export function useShowDevTools(): boolean {
  const { getSetting } = useSettings();
  return getSetting('advanced.show_dev_tools', false);
}

export function useStartPage(): string {
  const { getSetting } = useSettings();
  return getSetting('general.start_page', '/dashboard');
}

export function useDefaultProject(): string {
  const { getSetting } = useSettings();
  return getSetting('general.default_project', '');
}

export function useRecentItemsCount(): number {
  const { getSetting } = useSettings();
  return getSetting('general.recent_items_count', 10);
}

export function useTimezone(): string {
  const { getSetting } = useSettings();
  return getSetting('general.timezone', 'UTC');
}

export function useDateFormatPattern(): string {
  const { getSetting } = useSettings();
  return getSetting('general.date_format', 'YYYY-MM-DD');
}

/**
 * Date formatting hook that respects user timezone and format settings.
 * Returns formatting functions that can be used throughout the app.
 */
export function useDateFormat() {
  const timezone = useTimezone();
  const formatPattern = useDateFormatPattern();

  /**
   * Format a date string or Date object according to user settings.
   * @param date - Date string or Date object
   * @param includeTime - Whether to include time (default: false)
   */
  const formatDate = (date: string | Date | null | undefined, includeTime = false): string => {
    if (!date) return '';

    try {
      const d = typeof date === 'string' ? new Date(date) : date;
      if (isNaN(d.getTime())) return '';

      // Build Intl.DateTimeFormat options based on format pattern
      const options: Intl.DateTimeFormatOptions = {
        timeZone: timezone,
      };

      switch (formatPattern) {
        case 'YYYY-MM-DD':
          options.year = 'numeric';
          options.month = '2-digit';
          options.day = '2-digit';
          break;
        case 'MM/DD/YYYY':
          options.year = 'numeric';
          options.month = '2-digit';
          options.day = '2-digit';
          break;
        case 'DD/MM/YYYY':
          options.year = 'numeric';
          options.month = '2-digit';
          options.day = '2-digit';
          break;
        case 'MMM DD, YYYY':
          options.year = 'numeric';
          options.month = 'short';
          options.day = 'numeric';
          break;
        case 'DD MMM YYYY':
          options.year = 'numeric';
          options.month = 'short';
          options.day = 'numeric';
          break;
        default:
          options.year = 'numeric';
          options.month = '2-digit';
          options.day = '2-digit';
      }

      if (includeTime) {
        options.hour = '2-digit';
        options.minute = '2-digit';
      }

      // Use Intl.DateTimeFormat for locale-aware formatting
      const formatter = new Intl.DateTimeFormat('en-US', options);
      const parts = formatter.formatToParts(d);

      // Reconstruct based on our format pattern
      const getPart = (type: string) => parts.find(p => p.type === type)?.value || '';
      const year = getPart('year');
      const month = getPart('month');
      const day = getPart('day');
      const hour = getPart('hour');
      const minute = getPart('minute');

      let result: string;
      switch (formatPattern) {
        case 'YYYY-MM-DD':
          result = `${year}-${month}-${day}`;
          break;
        case 'MM/DD/YYYY':
          result = `${month}/${day}/${year}`;
          break;
        case 'DD/MM/YYYY':
          result = `${day}/${month}/${year}`;
          break;
        case 'MMM DD, YYYY':
          result = `${month} ${day}, ${year}`;
          break;
        case 'DD MMM YYYY':
          result = `${day} ${month} ${year}`;
          break;
        default:
          result = `${year}-${month}-${day}`;
      }

      if (includeTime && hour && minute) {
        result += ` ${hour}:${minute}`;
      }

      return result;
    } catch {
      return '';
    }
  };

  /**
   * Format a date with time according to user settings.
   */
  const formatDateTime = (date: string | Date | null | undefined): string => {
    return formatDate(date, true);
  };

  /**
   * Format a relative time (e.g., "2 hours ago", "yesterday").
   */
  const formatRelative = (date: string | Date | null | undefined): string => {
    if (!date) return '';

    try {
      const d = typeof date === 'string' ? new Date(date) : date;
      if (isNaN(d.getTime())) return '';

      const now = new Date();
      const diffMs = now.getTime() - d.getTime();
      const diffSeconds = Math.floor(diffMs / 1000);
      const diffMinutes = Math.floor(diffSeconds / 60);
      const diffHours = Math.floor(diffMinutes / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffSeconds < 60) return 'just now';
      if (diffMinutes < 60) return `${diffMinutes}m ago`;
      if (diffHours < 24) return `${diffHours}h ago`;
      if (diffDays === 1) return 'yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;

      // Fall back to formatted date
      return formatDate(d);
    } catch {
      return '';
    }
  };

  return {
    formatDate,
    formatDateTime,
    formatRelative,
    timezone,
    formatPattern,
  };
}

/** Clear the settings cache - useful after updating settings */
export function clearSettingsCache(): void {
  settingsCache = null;
}

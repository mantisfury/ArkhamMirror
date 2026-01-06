/**
 * useDebounce - Debounce hook for slider inputs
 *
 * Delays calling the callback until after the specified delay has passed
 * since the last call, preventing excessive updates during rapid changes.
 */

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Debounce a value - returns the debounced value after delay
 */
export function useDebounceValue<T>(value: T, delay: number = 100): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Debounce a callback - returns a debounced version of the callback
 */
export function useDebounceCallback<T extends (...args: any[]) => any>(
  callback: T,
  delay: number = 100
): T {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const callbackRef = useRef(callback);

  // Keep callback ref up to date
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  const debouncedCallback = useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
      }, delay);
    },
    [delay]
  ) as T;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return debouncedCallback;
}

/**
 * Slider with immediate local state + debounced parent updates
 *
 * This hook provides both immediate visual feedback and debounced updates.
 */
export function useDebouncedSlider<T>(
  externalValue: T,
  onChange: (value: T) => void,
  delay: number = 100
): [T, (value: T) => void] {
  const [localValue, setLocalValue] = useState<T>(externalValue);
  const debouncedOnChange = useDebounceCallback(onChange, delay);

  // Sync local value when external value changes (e.g., preset applied)
  useEffect(() => {
    setLocalValue(externalValue);
  }, [externalValue]);

  const handleChange = useCallback(
    (value: T) => {
      setLocalValue(value);  // Immediate update for visual feedback
      debouncedOnChange(value);  // Debounced update to parent
    },
    [debouncedOnChange]
  );

  return [localValue, handleChange];
}

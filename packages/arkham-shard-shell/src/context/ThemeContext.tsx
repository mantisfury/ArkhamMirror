/**
 * ThemeContext - Theme and appearance management
 *
 * Provides theme switching, accent color customization, and live CSS variable injection.
 * Themes: "arkham" (dark), "newsroom" (light parchment), "system" (follows OS preference)
 */

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

// Available theme presets
export type ThemePreset = 'arkham' | 'newsroom' | 'ocean' | 'forest' | 'frost' | 'midnight' | 'terminal' | 'system';

// Theme color definitions
interface ThemeColors {
  bgPrimary: string;
  bgSecondary: string;
  bgTertiary: string;
  bgHover: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  border: string;
  shadow: string;
}

// Theme definitions
const THEMES: Record<Exclude<ThemePreset, 'system'>, ThemeColors> = {
  arkham: {
    // Dark cyberpunk theme (current default)
    bgPrimary: '#1a1a2e',
    bgSecondary: '#16213e',
    bgTertiary: '#0f3460',
    bgHover: '#1e3a5f',
    textPrimary: '#eaeaea',
    textSecondary: '#a0a0a0',
    textMuted: '#6b6b6b',
    border: '#2a2a4a',
    shadow: 'rgba(0, 0, 0, 0.4)',
  },
  newsroom: {
    // Light parchment theme for document work
    bgPrimary: '#f5f0e6',      // Warm parchment
    bgSecondary: '#ebe5d9',    // Slightly darker parchment
    bgTertiary: '#e0d9c8',     // Card backgrounds
    bgHover: '#d5cebf',        // Hover states
    textPrimary: '#2c2416',    // Dark brown/black text
    textSecondary: '#5a4d3a',  // Medium brown
    textMuted: '#8a7b65',      // Light brown
    border: '#c9c0ad',         // Subtle borders
    shadow: 'rgba(0, 0, 0, 0.1)',
  },
  ocean: {
    // Deep blue dark theme - calming data immersion
    bgPrimary: '#0a1628',      // Deep ocean
    bgSecondary: '#0f2137',    // Midnight blue
    bgTertiary: '#1a3a5c',     // Sea depth
    bgHover: '#234e75',        // Current
    textPrimary: '#e6f1ff',    // Seafoam white
    textSecondary: '#8bb8d9',  // Wave
    textMuted: '#5a8ab0',      // Muted blue
    border: '#1e4060',         // Deep border
    shadow: 'rgba(0, 20, 40, 0.5)',
  },
  forest: {
    // Nature dark theme - organic, calming
    bgPrimary: '#1a2416',      // Deep forest green-black
    bgSecondary: '#243320',    // Dark moss
    bgTertiary: '#2d4228',     // Forest shadow
    bgHover: '#3a5535',        // Fern green
    textPrimary: '#e8f0e4',    // Soft white-green
    textSecondary: '#a8c4a0',  // Sage
    textMuted: '#6b8c62',      // Muted olive
    border: '#3a4a35',         // Dark bark
    shadow: 'rgba(0, 20, 0, 0.4)',
  },
  frost: {
    // Cool light theme - clean modern SaaS
    bgPrimary: '#f0f4f8',      // Ice white
    bgSecondary: '#e2e8f0',    // Frost
    bgTertiary: '#cbd5e1',     // Cool gray
    bgHover: '#94a3b8',        // Steel
    textPrimary: '#1e293b',    // Slate dark
    textSecondary: '#475569',  // Slate medium
    textMuted: '#64748b',      // Slate light
    border: '#cbd5e1',         // Cool border
    shadow: 'rgba(100, 116, 139, 0.15)',
  },
  midnight: {
    // Pure dark OLED theme - maximum contrast
    bgPrimary: '#000000',      // True black
    bgSecondary: '#0a0a0a',    // Near black
    bgTertiary: '#141414',     // Card dark
    bgHover: '#1f1f1f',        // Hover
    textPrimary: '#ffffff',    // Pure white
    textSecondary: '#a3a3a3',  // Gray
    textMuted: '#525252',      // Muted
    border: '#262626',         // Subtle border
    shadow: 'rgba(0, 0, 0, 0.8)',
  },
  terminal: {
    // Hacker green theme - retro aesthetic
    bgPrimary: '#0c0c0c',      // Terminal black
    bgSecondary: '#1a1a1a',    // Slightly lighter
    bgTertiary: '#2a2a2a',     // Card
    bgHover: '#3a3a3a',        // Hover
    textPrimary: '#33ff33',    // Matrix green
    textSecondary: '#22cc22',  // Darker green
    textMuted: '#119911',      // Muted green
    border: '#1a3a1a',         // Green tint border
    shadow: 'rgba(51, 255, 51, 0.1)',
  },
};

// Default accent color
const DEFAULT_ACCENT = '#e94560';

interface ThemeContextValue {
  // Current settings
  themePreset: ThemePreset;
  accentColor: string;
  effectiveTheme: Exclude<ThemePreset, 'system'>; // Resolved theme after system preference

  // Actions
  setThemePreset: (preset: ThemePreset) => void;
  setAccentColor: (color: string) => void;
  resetToDefaults: () => void;

  // State
  isLoading: boolean;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

// LocalStorage keys
const STORAGE_KEYS = {
  theme: 'arkham-theme-preset',
  accent: 'arkham-accent-color',
};

// Apply theme colors to CSS variables
function applyTheme(themeName: Exclude<ThemePreset, 'system'>, accentColor: string) {
  const theme = THEMES[themeName];
  const root = document.documentElement;

  // Apply theme colors
  root.style.setProperty('--arkham-bg-primary', theme.bgPrimary);
  root.style.setProperty('--arkham-bg-secondary', theme.bgSecondary);
  root.style.setProperty('--arkham-bg-tertiary', theme.bgTertiary);
  root.style.setProperty('--arkham-text-primary', theme.textPrimary);
  root.style.setProperty('--arkham-text-secondary', theme.textSecondary);
  root.style.setProperty('--arkham-text-muted', theme.textMuted);
  root.style.setProperty('--arkham-border', theme.border);

  // Convenience aliases used in some components
  root.style.setProperty('--bg-primary', theme.bgPrimary);
  root.style.setProperty('--bg-secondary', theme.bgSecondary);
  root.style.setProperty('--bg-tertiary', theme.bgTertiary);
  root.style.setProperty('--bg-hover', theme.bgHover);
  root.style.setProperty('--text-primary', theme.textPrimary);
  root.style.setProperty('--text-secondary', theme.textSecondary);
  root.style.setProperty('--text-muted', theme.textMuted);
  root.style.setProperty('--border-color', theme.border);

  // Update shadows for theme
  root.style.setProperty('--arkham-shadow-sm', `0 1px 2px ${theme.shadow}`);
  root.style.setProperty('--arkham-shadow-md', `0 4px 6px ${theme.shadow}`);
  root.style.setProperty('--arkham-shadow-lg', `0 10px 15px ${theme.shadow}`);

  // Apply accent color
  root.style.setProperty('--arkham-accent-primary', accentColor);
  root.style.setProperty('--accent-color', accentColor);

  // Generate accent color variants
  const accentDim = hexToRgba(accentColor, 0.15);
  root.style.setProperty('--accent-color-dim', accentDim);

  // Set data attribute for CSS selectors
  root.setAttribute('data-theme', themeName);
}

// Helper to convert hex to rgba
function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Get system preference
function getSystemTheme(): Exclude<ThemePreset, 'system'> {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'newsroom' : 'arkham';
  }
  return 'arkham';
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [isLoading, setIsLoading] = useState(true);
  const [themePreset, setThemePresetState] = useState<ThemePreset>('arkham');
  const [accentColor, setAccentColorState] = useState(DEFAULT_ACCENT);
  const [effectiveTheme, setEffectiveTheme] = useState<Exclude<ThemePreset, 'system'>>('arkham');

  // Load saved preferences on mount
  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem(STORAGE_KEYS.theme) as ThemePreset | null;
      const savedAccent = localStorage.getItem(STORAGE_KEYS.accent);

      const validThemes: ThemePreset[] = ['arkham', 'newsroom', 'ocean', 'forest', 'frost', 'midnight', 'terminal', 'system'];
      if (savedTheme && validThemes.includes(savedTheme)) {
        setThemePresetState(savedTheme);
      }
      if (savedAccent && /^#[0-9A-Fa-f]{6}$/.test(savedAccent)) {
        setAccentColorState(savedAccent);
      }
    } catch (e) {
      // Ignore storage errors
    }
    setIsLoading(false);
  }, []);

  // Resolve effective theme from preset
  useEffect(() => {
    if (themePreset === 'system') {
      setEffectiveTheme(getSystemTheme());
    } else {
      setEffectiveTheme(themePreset);
    }
  }, [themePreset]);

  // Listen for system preference changes
  useEffect(() => {
    if (themePreset !== 'system') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)');
    const handler = (e: MediaQueryListEvent) => {
      setEffectiveTheme(e.matches ? 'newsroom' : 'arkham');
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
  }, [themePreset]);

  // Apply theme whenever effective theme or accent changes
  useEffect(() => {
    if (!isLoading) {
      applyTheme(effectiveTheme, accentColor);
    }
  }, [effectiveTheme, accentColor, isLoading]);

  const setThemePreset = useCallback((preset: ThemePreset) => {
    setThemePresetState(preset);
    try {
      localStorage.setItem(STORAGE_KEYS.theme, preset);
    } catch (e) {
      // Ignore storage errors
    }
  }, []);

  const setAccentColor = useCallback((color: string) => {
    // Validate hex color
    if (!/^#[0-9A-Fa-f]{6}$/.test(color)) return;

    setAccentColorState(color);
    try {
      localStorage.setItem(STORAGE_KEYS.accent, color);
    } catch (e) {
      // Ignore storage errors
    }
  }, []);

  const resetToDefaults = useCallback(() => {
    setThemePreset('arkham');
    setAccentColor(DEFAULT_ACCENT);
  }, [setThemePreset, setAccentColor]);

  return (
    <ThemeContext.Provider
      value={{
        themePreset,
        accentColor,
        effectiveTheme,
        setThemePreset,
        setAccentColor,
        resetToDefaults,
        isLoading,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}

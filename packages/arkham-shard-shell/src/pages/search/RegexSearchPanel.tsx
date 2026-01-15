/**
 * Regex Search Panel
 *
 * A dedicated panel for regex pattern searching with preset support.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useRegexSearch, useRegexPresets, useDetectedPatterns, validatePattern } from './api';
import type { RegexPreset, RegexMatch, PatternValidation, DetectedPattern } from './types';
import './RegexSearchPanel.css';

interface RegexSearchPanelProps {
  projectId?: string;
  onMatchClick?: (match: RegexMatch) => void;
}

const CATEGORY_ICONS: Record<string, string> = {
  contact: 'Mail',
  pii: 'Shield',
  financial: 'DollarSign',
  technical: 'Globe',
  temporal: 'Calendar',
  custom: 'Hash',
};

const PATTERN_TYPE_ICONS: Record<string, string> = {
  recurring_theme: 'Repeat',
  behavioral: 'Activity',
  temporal: 'Clock',
  correlation: 'Link',
  linguistic: 'Type',
  structural: 'Layout',
  custom: 'Settings',
};

export default function RegexSearchPanel({ projectId, onMatchClick }: RegexSearchPanelProps) {
  const [pattern, setPattern] = useState('');
  const [searchPattern, setSearchPattern] = useState('');
  const [flags, setFlags] = useState<string[]>([]);
  const [showPresets, setShowPresets] = useState(true);
  const [showDetected, setShowDetected] = useState(true);
  const [validation, setValidation] = useState<PatternValidation | null>(null);
  const [validating, setValidating] = useState(false);

  const { data: presets, loading: presetsLoading } = useRegexPresets();
  const { data: detectedPatterns, loading: detectedLoading } = useDetectedPatterns({ limit: 50 });
  const {
    data: searchResults,
    loading: searchLoading,
    error: searchError,
  } = useRegexSearch({
    pattern: searchPattern,
    request: { flags, project_id: projectId, limit: 100 },
    enabled: !!searchPattern, // Allow search even without validation - backend validates
  });

  // Validate pattern on change (debounced)
  useEffect(() => {
    if (!pattern) {
      setValidation(null);
      return;
    }

    const timer = setTimeout(async () => {
      setValidating(true);
      try {
        const result = await validatePattern(pattern);
        setValidation(result);
      } catch {
        setValidation({ valid: false, error: 'Validation failed', estimated_performance: 'invalid' });
      } finally {
        setValidating(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [pattern]);

  const handleSearch = useCallback(() => {
    // Allow search even if validation hasn't completed yet - backend will validate
    if (pattern.trim()) {
      setSearchPattern(pattern);
    }
  }, [pattern]);

  const handlePresetClick = useCallback((preset: RegexPreset) => {
    setPattern(preset.pattern);
    setFlags(preset.flags || []);
  }, []);

  const handleDetectedPatternClick = useCallback((detected: DetectedPattern) => {
    // Use the first regex pattern from criteria if available
    if (detected.criteria?.regex_patterns?.length) {
      setPattern(detected.criteria.regex_patterns[0]);
      setFlags([]);
    } else if (detected.criteria?.keywords?.length) {
      // Fall back to keyword as a simple pattern
      setPattern(detected.criteria.keywords.join('|'));
      setFlags(['case_insensitive']);
    }
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && pattern.trim()) {
        handleSearch();
      }
    },
    [handleSearch, pattern]
  );

  const toggleFlag = useCallback((flag: string) => {
    setFlags((prev) => (prev.includes(flag) ? prev.filter((f) => f !== flag) : [...prev, flag]));
  }, []);

  // Group presets by category
  const presetsByCategory = presets.reduce((acc, preset) => {
    const cat = preset.category || 'custom';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(preset);
    return acc;
  }, {} as Record<string, RegexPreset[]>);

  // Filter and group detected patterns that have searchable criteria
  const searchableDetectedPatterns = detectedPatterns.filter(
    (p) => p.criteria?.regex_patterns?.length || p.criteria?.keywords?.length
  );

  // Group detected patterns by type
  const detectedByType = searchableDetectedPatterns.reduce((acc, pattern) => {
    const type = pattern.pattern_type || 'custom';
    if (!acc[type]) acc[type] = [];
    acc[type].push(pattern);
    return acc;
  }, {} as Record<string, DetectedPattern[]>);

  const getPerformanceClass = (perf: string) => {
    switch (perf) {
      case 'fast': return 'regex-perf-fast';
      case 'moderate': return 'regex-perf-moderate';
      case 'slow': return 'regex-perf-slow';
      case 'dangerous': return 'regex-perf-dangerous';
      default: return 'regex-perf-invalid';
    }
  };

  return (
    <div className="regex-panel">
      {/* Pattern Input */}
      <div className="regex-input-section">
        <div className="regex-input-row">
          <div className="regex-input-wrapper">
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Enter regex pattern (e.g., \d{3}-\d{4})"
              className="regex-input"
            />
            {validating && (
              <div className="regex-input-icon">
                <Icon name="Loader2" size={16} className="spin" />
              </div>
            )}
            {!validating && validation && (
              <div className="regex-input-icon">
                {validation.valid ? (
                  <Icon name="CheckCircle" size={16} className={getPerformanceClass(validation.estimated_performance)} />
                ) : (
                  <Icon name="AlertTriangle" size={16} className="regex-perf-invalid" />
                )}
              </div>
            )}
          </div>
          <button
            onClick={handleSearch}
            disabled={!pattern.trim() || searchLoading}
            className="btn btn-primary"
          >
            <Icon name="Search" size={16} />
            Search
          </button>
        </div>

        {/* Validation Feedback */}
        {validation && (
          <div className="regex-validation">
            {validation.valid ? (
              <div className={`regex-validation-msg ${getPerformanceClass(validation.estimated_performance)}`}>
                <Icon name="Zap" size={14} />
                <span>Performance: {validation.estimated_performance}</span>
                {validation.estimated_performance === 'dangerous' && (
                  <span className="regex-validation-warning">
                    (may cause slowdowns on large datasets)
                  </span>
                )}
              </div>
            ) : (
              <div className="regex-validation-msg regex-perf-invalid">
                <Icon name="AlertTriangle" size={14} />
                <span>{validation.error}</span>
              </div>
            )}
          </div>
        )}

        {/* Regex Flags */}
        <div className="regex-flags">
          <span className="regex-flags-label">Flags:</span>
          {[
            { id: 'case_insensitive', label: 'Case Insensitive', short: 'i' },
            { id: 'multiline', label: 'Multiline', short: 'm' },
            { id: 'dotall', label: 'Dot All', short: 's' },
          ].map((flag) => (
            <button
              key={flag.id}
              onClick={() => toggleFlag(flag.id)}
              className={`regex-flag-btn ${flags.includes(flag.id) ? 'active' : ''}`}
              title={flag.label}
            >
              {flag.short}
            </button>
          ))}
        </div>
      </div>

      {/* Presets Section */}
      <div className="regex-presets-section">
        <button
          onClick={() => setShowPresets(!showPresets)}
          className="regex-presets-toggle"
        >
          <span>Pattern Presets</span>
          <Icon name={showPresets ? 'ChevronUp' : 'ChevronDown'} size={16} />
        </button>

        {showPresets && (
          <div className="regex-presets-content">
            {presetsLoading ? (
              <div className="regex-presets-loading">Loading presets...</div>
            ) : (
              Object.entries(presetsByCategory).map(([category, categoryPresets]) => (
                <div key={category} className="regex-preset-category">
                  <div className="regex-preset-category-header">
                    <Icon name={CATEGORY_ICONS[category] || 'Hash'} size={12} />
                    <span>{category}</span>
                  </div>
                  <div className="regex-preset-list">
                    {categoryPresets.map((preset) => (
                      <button
                        key={preset.id}
                        onClick={() => handlePresetClick(preset)}
                        className="regex-preset-btn"
                        title={`${preset.description}\n\nPattern: ${preset.pattern}`}
                      >
                        {preset.name}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Detected Patterns from Ingest Section */}
      <div className="regex-presets-section">
        <button
          onClick={() => setShowDetected(!showDetected)}
          className="regex-presets-toggle"
        >
          <span>Detected Patterns</span>
          {searchableDetectedPatterns.length > 0 && (
            <span className="regex-detected-badge">{searchableDetectedPatterns.length}</span>
          )}
          <Icon name={showDetected ? 'ChevronUp' : 'ChevronDown'} size={16} />
        </button>

        {showDetected && (
          <div className="regex-presets-content">
            {detectedLoading ? (
              <div className="regex-presets-loading">Loading detected patterns...</div>
            ) : searchableDetectedPatterns.length === 0 ? (
              <div className="regex-detected-empty">
                <Icon name="Info" size={14} />
                <span>No patterns detected yet. Process documents to auto-detect patterns.</span>
              </div>
            ) : (
              Object.entries(detectedByType).map(([type, typePatterns]) => (
                <div key={type} className="regex-preset-category">
                  <div className="regex-preset-category-header">
                    <Icon name={PATTERN_TYPE_ICONS[type] || 'Hash'} size={12} />
                    <span>{type.replace(/_/g, ' ')}</span>
                  </div>
                  <div className="regex-preset-list">
                    {typePatterns.map((detected) => (
                      <button
                        key={detected.id}
                        onClick={() => handleDetectedPatternClick(detected)}
                        className={`regex-preset-btn regex-detected-status-${detected.status}`}
                        title={`${detected.description || detected.name}\n\nMatches: ${detected.match_count}\nConfidence: ${(detected.confidence * 100).toFixed(0)}%\nStatus: ${detected.status}`}
                      >
                        {detected.name}
                        {detected.match_count > 0 && (
                          <span className="regex-detected-count">{detected.match_count}</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Results Section */}
      <div className="regex-results">
        {searchLoading && (
          <div className="regex-results-loading">
            <Icon name="Loader2" size={24} className="spin" />
            <span>Searching...</span>
          </div>
        )}

        {searchError && (
          <div className="regex-results-error">
            <Icon name="AlertTriangle" size={20} />
            <span>{searchError.message}</span>
          </div>
        )}

        {searchResults && !searchLoading && (
          <>
            {/* Results Header */}
            <div className="regex-results-header">
              <span>
                Found <strong>{searchResults.total_matches}</strong> matches
                in <strong>{searchResults.documents_searched}</strong> documents
              </span>
              <span>{searchResults.duration_ms.toFixed(1)}ms</span>
            </div>

            {/* Match List */}
            <div className="regex-match-list">
              {searchResults.matches.length === 0 ? (
                <div className="regex-results-empty">
                  <Icon name="Info" size={32} />
                  <p>No matches found for this pattern</p>
                </div>
              ) : (
                searchResults.matches.map((match, index) => (
                  <div
                    key={`${match.chunk_id}-${index}`}
                    className="regex-match-item"
                    onClick={() => onMatchClick?.(match)}
                  >
                    <Icon name="FileText" size={18} />
                    <div className="regex-match-content">
                      <div className="regex-match-header">
                        <span className="regex-match-title">{match.document_title}</span>
                        {match.page_number && (
                          <span className="regex-match-badge">Page {match.page_number}</span>
                        )}
                        <span className="regex-match-badge">Line {match.line_number}</span>
                      </div>
                      <div className="regex-match-context">
                        {match.context.split(match.match_text).map((part, i, arr) => (
                          <React.Fragment key={i}>
                            <span className="regex-context-text">{part}</span>
                            {i < arr.length - 1 && (
                              <span className="regex-match-highlight">{match.match_text}</span>
                            )}
                          </React.Fragment>
                        ))}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </>
        )}

        {!searchResults && !searchLoading && !searchError && (
          <div className="regex-results-empty">
            <Icon name="Search" size={32} />
            <p>Enter a regex pattern and click Search</p>
            <p className="regex-results-hint">Or select a preset pattern above</p>
          </div>
        )}
      </div>
    </div>
  );
}

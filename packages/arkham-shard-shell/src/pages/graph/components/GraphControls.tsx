/**
 * GraphControls - Main container for all graph visualization controls
 */

import { useState } from 'react';
import { Icon } from '../../../components/common/Icon';
import { LabelControls } from './LabelControls';
import { LayoutControls } from './LayoutControls';
import { NodeSizeControls } from './NodeSizeControls';
import { FilterControls } from './FilterControls';
import { ScoringControls } from './ScoringControls';
import type { UseGraphSettingsReturn } from '../hooks/useGraphSettings';

interface GraphControlsProps {
  graphSettings: UseGraphSettingsReturn;
  availableEntityTypes: string[];
  availableDocumentSources?: { id: string; name: string }[];
  onRecalculateScores?: () => void;
  scoresLoading?: boolean;
  scoresError?: string | null;
}

type SectionId = 'labels' | 'layout' | 'nodeSize' | 'filters' | 'scoring';

export function GraphControls({
  graphSettings,
  availableEntityTypes,
  availableDocumentSources = [],
  onRecalculateScores,
  scoresLoading = false,
  scoresError = null
}: GraphControlsProps) {
  const [expandedSections, setExpandedSections] = useState<Set<SectionId>>(
    new Set(['labels', 'filters'])
  );
  const [showImportExport, setShowImportExport] = useState(false);
  const [importText, setImportText] = useState('');

  const {
    settings,
    updateLabels,
    updateLayout,
    updateNodeSize,
    updateFilters,
    updateScoring,
    updateScoringWeights,
    normalizedWeights,
    applyPreset,
    reset,
    exportSettings,
    importSettings
  } = graphSettings;

  const toggleSection = (id: SectionId) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleExport = () => {
    const json = exportSettings();
    navigator.clipboard.writeText(json);
    // Could show toast here
  };

  const handleImport = () => {
    if (importSettings(importText)) {
      setImportText('');
      setShowImportExport(false);
      // Could show success toast
    } else {
      // Could show error toast
    }
  };

  return (
    <div className="graph-controls">
      {/* Presets Bar */}
      <div className="controls-header">
        <h3>Graph Controls</h3>
        <div className="preset-buttons">
          <button
            className="preset-btn"
            onClick={() => applyPreset('performance')}
            title="Optimized for large graphs"
          >
            <Icon name="Zap" size={14} />
            Fast
          </button>
          <button
            className="preset-btn"
            onClick={() => applyPreset('balanced')}
            title="Balanced settings"
          >
            <Icon name="Scale" size={14} />
            Balanced
          </button>
          <button
            className="preset-btn"
            onClick={() => applyPreset('detail')}
            title="Maximum detail"
          >
            <Icon name="Eye" size={14} />
            Detail
          </button>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="controls-actions">
        <button className="action-btn" onClick={reset} title="Reset to defaults">
          <Icon name="RotateCcw" size={14} />
          Reset
        </button>
        <button
          className="action-btn"
          onClick={() => setShowImportExport(!showImportExport)}
          title="Import/Export settings"
        >
          <Icon name="Settings2" size={14} />
          Import/Export
        </button>
      </div>

      {/* Import/Export Panel */}
      {showImportExport && (
        <div className="import-export-panel">
          <div className="import-export-row">
            <button className="action-btn" onClick={handleExport}>
              <Icon name="Copy" size={14} />
              Copy to Clipboard
            </button>
          </div>
          <div className="import-export-row">
            <textarea
              value={importText}
              onChange={e => setImportText(e.target.value)}
              placeholder="Paste settings JSON here..."
              className="import-textarea"
              rows={4}
            />
            <button
              className="action-btn"
              onClick={handleImport}
              disabled={!importText}
            >
              <Icon name="Download" size={14} />
              Import
            </button>
          </div>
        </div>
      )}

      {/* Collapsible Sections */}
      <div className="controls-sections">
        {/* Labels Section */}
        <div className={`section-wrapper ${expandedSections.has('labels') ? 'expanded' : ''}`}>
          <button
            className="section-toggle"
            onClick={() => toggleSection('labels')}
          >
            <Icon name="Tag" size={16} />
            <span>Labels</span>
            <Icon
              name="ChevronDown"
              size={16}
              className={`toggle-icon ${expandedSections.has('labels') ? 'rotated' : ''}`}
            />
          </button>
          {expandedSections.has('labels') && (
            <LabelControls settings={settings.labels} onChange={updateLabels} />
          )}
        </div>

        {/* Node Size Section */}
        <div className={`section-wrapper ${expandedSections.has('nodeSize') ? 'expanded' : ''}`}>
          <button
            className="section-toggle"
            onClick={() => toggleSection('nodeSize')}
          >
            <Icon name="Circle" size={16} />
            <span>Node Size</span>
            <Icon
              name="ChevronDown"
              size={16}
              className={`toggle-icon ${expandedSections.has('nodeSize') ? 'rotated' : ''}`}
            />
          </button>
          {expandedSections.has('nodeSize') && (
            <NodeSizeControls settings={settings.nodeSize} onChange={updateNodeSize} />
          )}
        </div>

        {/* Layout Section */}
        <div className={`section-wrapper ${expandedSections.has('layout') ? 'expanded' : ''}`}>
          <button
            className="section-toggle"
            onClick={() => toggleSection('layout')}
          >
            <Icon name="Move" size={16} />
            <span>Layout & Physics</span>
            <Icon
              name="ChevronDown"
              size={16}
              className={`toggle-icon ${expandedSections.has('layout') ? 'rotated' : ''}`}
            />
          </button>
          {expandedSections.has('layout') && (
            <LayoutControls settings={settings.layout} onChange={updateLayout} />
          )}
        </div>

        {/* Filters Section */}
        <div className={`section-wrapper ${expandedSections.has('filters') ? 'expanded' : ''}`}>
          <button
            className="section-toggle"
            onClick={() => toggleSection('filters')}
          >
            <Icon name="Filter" size={16} />
            <span>Filters</span>
            <Icon
              name="ChevronDown"
              size={16}
              className={`toggle-icon ${expandedSections.has('filters') ? 'rotated' : ''}`}
            />
          </button>
          {expandedSections.has('filters') && (
            <FilterControls
              settings={settings.filters}
              onChange={updateFilters}
              availableEntityTypes={availableEntityTypes}
              availableDocumentSources={availableDocumentSources}
            />
          )}
        </div>

        {/* Scoring Section */}
        <div className={`section-wrapper ${expandedSections.has('scoring') ? 'expanded' : ''}`}>
          <button
            className="section-toggle"
            onClick={() => toggleSection('scoring')}
          >
            <Icon name="BarChart2" size={16} />
            <span>Smart Weighting</span>
            {settings.scoring.enabled && (
              <span className="section-badge">ON</span>
            )}
            <Icon
              name="ChevronDown"
              size={16}
              className={`toggle-icon ${expandedSections.has('scoring') ? 'rotated' : ''}`}
            />
          </button>
          {expandedSections.has('scoring') && (
            <ScoringControls
              settings={settings.scoring}
              normalizedWeights={normalizedWeights}
              onChange={updateScoring}
              onWeightChange={updateScoringWeights}
              onRecalculate={onRecalculateScores}
              isLoading={scoresLoading}
              error={scoresError}
            />
          )}
        </div>
      </div>
    </div>
  );
}

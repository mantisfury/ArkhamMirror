/**
 * LayoutModeControls - Layout algorithm selection and configuration
 *
 * Allows users to switch between different graph layout algorithms
 * and configure algorithm-specific options.
 */

import { Icon } from '../../../components/common/Icon';
import type { LayoutSettings, LayoutType, LayoutDirection } from '../hooks/useGraphSettings';
import { useDebouncedSlider } from '../hooks/useDebounce';

interface LayoutModeControlsProps {
  settings: LayoutSettings;
  onChange: (updates: Partial<LayoutSettings>) => void;
  selectedNodeId?: string | null;  // For "use as root" action
  entityTypes?: string[];  // Available entity types for bipartite
  onApplyLayout?: () => void;  // Callback to trigger layout recalculation
  isCalculating?: boolean;
}

interface LayoutOption {
  id: LayoutType;
  name: string;
  icon: string;
  description: string;
  frontendOnly?: boolean;
}

const LAYOUT_OPTIONS: LayoutOption[] = [
  {
    id: 'force',
    name: 'Force-Directed',
    icon: 'Orbit',
    description: 'Physics simulation that clusters connected nodes',
    frontendOnly: true,
  },
  {
    id: 'hierarchical',
    name: 'Hierarchical',
    icon: 'GitBranch',
    description: 'Layered layout for org charts and command structures',
  },
  {
    id: 'radial',
    name: 'Radial',
    icon: 'Circle',
    description: 'Concentric circles from a center node',
  },
  {
    id: 'tree',
    name: 'Tree',
    icon: 'Network',
    description: 'Classic tree structure layout',
  },
  {
    id: 'circular',
    name: 'Circular',
    icon: 'CircleDot',
    description: 'All nodes arranged on a circle',
  },
  {
    id: 'bipartite',
    name: 'Bipartite',
    icon: 'Columns',
    description: 'Two-column layout by entity type',
  },
  {
    id: 'grid',
    name: 'Grid',
    icon: 'Grid3X3',
    description: 'Simple grid arrangement',
  },
];

const DIRECTION_OPTIONS: { id: LayoutDirection; label: string }[] = [
  { id: 'TB', label: 'Top to Bottom' },
  { id: 'BT', label: 'Bottom to Top' },
  { id: 'LR', label: 'Left to Right' },
  { id: 'RL', label: 'Right to Left' },
];

export function LayoutModeControls({
  settings,
  onChange,
  selectedNodeId,
  entityTypes = [],
  onApplyLayout,
  isCalculating = false,
}: LayoutModeControlsProps) {
  // Debounced sliders for spacing
  const [layerSpacing, setLayerSpacing] = useDebouncedSlider(
    settings.layerSpacing,
    (v) => onChange({ layerSpacing: v }),
    100
  );
  const [nodeSpacing, setNodeSpacing] = useDebouncedSlider(
    settings.nodeSpacing,
    (v) => onChange({ nodeSpacing: v }),
    100
  );
  const [radiusStep, setRadiusStep] = useDebouncedSlider(
    settings.radiusStep,
    (v) => onChange({ radiusStep: v }),
    100
  );
  const [radius, setRadius] = useDebouncedSlider(
    settings.radius,
    (v) => onChange({ radius: v }),
    100
  );

  const currentLayout = LAYOUT_OPTIONS.find(l => l.id === settings.layoutType);
  const showRootNodeOption = ['hierarchical', 'radial', 'tree'].includes(settings.layoutType);
  const showDirectionOption = ['hierarchical', 'tree'].includes(settings.layoutType);
  const showSpacingOptions = ['hierarchical', 'tree'].includes(settings.layoutType);
  const showRadiusOptions = settings.layoutType === 'radial';
  const showCircularOptions = settings.layoutType === 'circular';
  const showBipartiteOptions = settings.layoutType === 'bipartite';
  const showGridOptions = settings.layoutType === 'grid';

  // Handle using selected node as root
  const handleUseSelectedAsRoot = () => {
    if (selectedNodeId) {
      onChange({ rootNodeId: selectedNodeId });
    }
  };

  return (
    <div className="control-section">
      <div className="control-header">
        <Icon name="LayoutGrid" size={16} />
        <h4>Layout Mode</h4>
      </div>

      {/* Layout Type Selection */}
      <div className="control-group">
        <label>Layout Algorithm</label>
        <div className="layout-grid">
          {LAYOUT_OPTIONS.map(option => (
            <button
              key={option.id}
              className={`layout-option ${settings.layoutType === option.id ? 'active' : ''}`}
              onClick={() => onChange({ layoutType: option.id })}
              title={option.description}
            >
              <Icon name={option.icon} size={18} />
              <span>{option.name}</span>
            </button>
          ))}
        </div>
        {currentLayout && (
          <span className="control-hint">{currentLayout.description}</span>
        )}
      </div>

      {/* Apply Layout Button (for server-calculated layouts) */}
      {settings.layoutType !== 'force' && (
        <div className="control-group">
          <button
            className="apply-layout-btn"
            onClick={onApplyLayout}
            disabled={isCalculating}
          >
            {isCalculating ? (
              <>
                <Icon name="Loader2" size={16} className="spin" />
                <span>Calculating...</span>
              </>
            ) : (
              <>
                <Icon name="RefreshCw" size={16} />
                <span>Apply Layout</span>
              </>
            )}
          </button>
          <span className="control-hint">Recalculate node positions</span>
        </div>
      )}

      {/* Root Node Selection */}
      {showRootNodeOption && (
        <div className="control-group">
          <label>Root Node</label>
          <div className="root-node-control">
            <input
              type="text"
              value={settings.rootNodeId || ''}
              onChange={(e) => onChange({ rootNodeId: e.target.value || null })}
              placeholder="Auto-detect (highest degree)"
              className="control-input"
            />
            {selectedNodeId && (
              <button
                className="use-selected-btn"
                onClick={handleUseSelectedAsRoot}
                title="Use currently selected node as root"
              >
                <Icon name="Target" size={14} />
                Use Selected
              </button>
            )}
          </div>
          <span className="control-hint">
            {settings.rootNodeId
              ? `Using: ${settings.rootNodeId}`
              : 'Will use node with highest degree'}
          </span>
        </div>
      )}

      {/* Direction Selection */}
      {showDirectionOption && (
        <div className="control-group">
          <label>Direction</label>
          <select
            value={settings.direction}
            onChange={(e) => onChange({ direction: e.target.value as LayoutDirection })}
            className="control-select"
          >
            {DIRECTION_OPTIONS.map(opt => (
              <option key={opt.id} value={opt.id}>{opt.label}</option>
            ))}
          </select>
          <span className="control-hint">Flow direction of hierarchy</span>
        </div>
      )}

      {/* Spacing Options (Hierarchical/Tree) */}
      {showSpacingOptions && (
        <>
          <div className="control-group">
            <label>Layer Spacing: {layerSpacing}px</label>
            <input
              type="range"
              min="50"
              max="200"
              value={layerSpacing}
              onChange={(e) => setLayerSpacing(Number(e.target.value))}
              className="control-slider"
            />
            <span className="control-hint">Distance between hierarchy levels</span>
          </div>

          <div className="control-group">
            <label>Node Spacing: {nodeSpacing}px</label>
            <input
              type="range"
              min="20"
              max="100"
              value={nodeSpacing}
              onChange={(e) => setNodeSpacing(Number(e.target.value))}
              className="control-slider"
            />
            <span className="control-hint">Distance between sibling nodes</span>
          </div>
        </>
      )}

      {/* Radial Options */}
      {showRadiusOptions && (
        <div className="control-group">
          <label>Radius Step: {radiusStep}px</label>
          <input
            type="range"
            min="50"
            max="200"
            value={radiusStep}
            onChange={(e) => setRadiusStep(Number(e.target.value))}
            className="control-slider"
          />
          <span className="control-hint">Distance between concentric circles</span>
        </div>
      )}

      {/* Circular Options */}
      {showCircularOptions && (
        <div className="control-group">
          <label>Circle Radius: {radius}px</label>
          <input
            type="range"
            min="100"
            max="500"
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
            className="control-slider"
          />
          <span className="control-hint">Radius of the circle</span>
        </div>
      )}

      {/* Bipartite Options */}
      {showBipartiteOptions && (
        <>
          <div className="control-group">
            <label>Left Column Types</label>
            <div className="type-chips">
              {(entityTypes.length > 0 ? entityTypes : ['document', 'person', 'organization', 'location', 'event']).map(type => (
                <button
                  key={type}
                  className={`type-chip ${settings.leftTypes.includes(type) ? 'active' : ''}`}
                  onClick={() => {
                    const newTypes = settings.leftTypes.includes(type)
                      ? settings.leftTypes.filter(t => t !== type)
                      : [...settings.leftTypes, type];
                    onChange({ leftTypes: newTypes });
                  }}
                >
                  {type}
                </button>
              ))}
            </div>
            <span className="control-hint">Entity types for left column</span>
          </div>

          <div className="control-group">
            <label>Right Column Types</label>
            <div className="type-chips">
              {(entityTypes.length > 0 ? entityTypes : ['document', 'person', 'organization', 'location', 'event']).map(type => (
                <button
                  key={type}
                  className={`type-chip ${settings.rightTypes.includes(type) ? 'active' : ''}`}
                  onClick={() => {
                    const newTypes = settings.rightTypes.includes(type)
                      ? settings.rightTypes.filter(t => t !== type)
                      : [...settings.rightTypes, type];
                    onChange({ rightTypes: newTypes });
                  }}
                >
                  {type}
                </button>
              ))}
            </div>
            <span className="control-hint">Entity types for right column</span>
          </div>
        </>
      )}

      {/* Grid Options */}
      {showGridOptions && (
        <div className="control-group">
          <label>Columns</label>
          <input
            type="number"
            min="1"
            max="20"
            value={settings.gridColumns || ''}
            onChange={(e) => onChange({ gridColumns: e.target.value ? Number(e.target.value) : null })}
            placeholder="Auto"
            className="control-input"
          />
          <span className="control-hint">Number of columns (auto if empty)</span>
        </div>
      )}
    </div>
  );
}

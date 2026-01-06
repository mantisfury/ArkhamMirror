/**
 * LayoutControls - Physics controls for the force-directed graph simulation
 *
 * Uses debounced sliders for smooth visual feedback with batched state updates.
 * These controls only apply when using the force-directed layout.
 */

import { Icon } from '../../../components/common/Icon';
import type { PhysicsSettings } from '../hooks/useGraphSettings';
import { useDebouncedSlider } from '../hooks/useDebounce';

interface LayoutControlsProps {
  settings: PhysicsSettings;
  onChange: (updates: Partial<PhysicsSettings>) => void;
  disabled?: boolean;  // Disable when using non-force layouts
}

export function LayoutControls({ settings, onChange, disabled = false }: LayoutControlsProps) {
  // Debounced sliders for performance (100ms delay)
  const [chargeStrength, setChargeStrength] = useDebouncedSlider(
    settings.chargeStrength,
    (v) => onChange({ chargeStrength: v }),
    100
  );
  const [linkDistance, setLinkDistance] = useDebouncedSlider(
    settings.linkDistance,
    (v) => onChange({ linkDistance: v }),
    100
  );
  const [linkStrength, setLinkStrength] = useDebouncedSlider(
    settings.linkStrength,
    (v) => onChange({ linkStrength: v }),
    100
  );
  const [centerStrength, setCenterStrength] = useDebouncedSlider(
    settings.centerStrength,
    (v) => onChange({ centerStrength: v }),
    100
  );
  const [collisionPadding, setCollisionPadding] = useDebouncedSlider(
    settings.collisionPadding,
    (v) => onChange({ collisionPadding: v }),
    100
  );
  const [alphaDecay, setAlphaDecay] = useDebouncedSlider(
    settings.alphaDecay,
    (v) => onChange({ alphaDecay: v }),
    100
  );

  return (
    <div className={`control-section ${disabled ? 'disabled' : ''}`}>
      <div className="control-header">
        <Icon name="Move" size={16} />
        <h4>Force Simulation</h4>
        {disabled && <span className="control-badge">Force layout only</span>}
      </div>

      <div className="control-group">
        <label>
          Node Repulsion: {chargeStrength}
        </label>
        <input
          type="range"
          min="-1000"
          max="-30"
          value={chargeStrength}
          onChange={e => setChargeStrength(Number(e.target.value))}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>Strong</span>
          <span>Weak</span>
        </div>
        <span className="control-hint">How strongly nodes push apart</span>
      </div>

      <div className="control-group">
        <label>
          Link Distance: {linkDistance}px
        </label>
        <input
          type="range"
          min="20"
          max="200"
          value={linkDistance}
          onChange={e => setLinkDistance(Number(e.target.value))}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>20</span>
          <span>110</span>
          <span>200</span>
        </div>
        <span className="control-hint">Target distance between connected nodes</span>
      </div>

      <div className="control-group">
        <label>
          Link Strength: {linkStrength.toFixed(2)}
        </label>
        <input
          type="range"
          min="0.1"
          max="1"
          step="0.05"
          value={linkStrength}
          onChange={e => setLinkStrength(Number(e.target.value))}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>Loose</span>
          <span>Tight</span>
        </div>
        <span className="control-hint">How rigidly links enforce distance</span>
      </div>

      <div className="control-group">
        <label>
          Center Gravity: {centerStrength.toFixed(2)}
        </label>
        <input
          type="range"
          min="0"
          max="0.3"
          step="0.01"
          value={centerStrength}
          onChange={e => setCenterStrength(Number(e.target.value))}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>None</span>
          <span>Strong</span>
        </div>
        <span className="control-hint">Pull toward center of view</span>
      </div>

      <div className="control-group">
        <label>
          Collision Padding: {collisionPadding}px
        </label>
        <input
          type="range"
          min="0"
          max="20"
          value={collisionPadding}
          onChange={e => setCollisionPadding(Number(e.target.value))}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>0</span>
          <span>10</span>
          <span>20</span>
        </div>
        <span className="control-hint">Extra space between nodes</span>
      </div>

      <div className="control-group">
        <label>
          Simulation Speed: {(alphaDecay * 1000).toFixed(0)}
        </label>
        <input
          type="range"
          min="0.01"
          max="0.05"
          step="0.005"
          value={alphaDecay}
          onChange={e => setAlphaDecay(Number(e.target.value))}
          className="control-slider"
        />
        <div className="slider-labels">
          <span>Slow</span>
          <span>Fast</span>
        </div>
        <span className="control-hint">How quickly layout stabilizes</span>
      </div>
    </div>
  );
}

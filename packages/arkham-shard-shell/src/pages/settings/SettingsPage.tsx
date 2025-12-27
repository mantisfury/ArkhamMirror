/**
 * SettingsPage - Application settings management
 *
 * Provides UI for viewing and modifying application settings.
 * Settings are organized by category with real-time updates.
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useFetch } from '../../hooks/useFetch';
import './SettingsPage.css';

// Types
interface Setting {
  key: string;
  value: unknown;
  default_value: unknown;
  category: string;
  data_type: string;
  label: string;
  description: string;
  requires_restart: boolean;
  is_modified: boolean;
  is_readonly: boolean;
  order: number;
  options: Array<{ value: string | number; label: string }>;
  validation: Record<string, unknown>;
}

interface CategoryInfo {
  id: string;
  label: string;
  icon: string;
  description: string;
}

const CATEGORIES: CategoryInfo[] = [
  { id: 'general', label: 'General', icon: 'Settings', description: 'Language, timezone, and date formats' },
  { id: 'appearance', label: 'Appearance', icon: 'Palette', description: 'Theme, colors, and layout' },
  { id: 'notifications', label: 'Notifications', icon: 'Bell', description: 'Alert preferences' },
  { id: 'performance', label: 'Performance', icon: 'Zap', description: 'Caching and pagination' },
  { id: 'privacy', label: 'Privacy', icon: 'Shield', description: 'Data and analytics settings' },
  { id: 'advanced', label: 'Advanced', icon: 'Wrench', description: 'Developer and debug options' },
];

export function SettingsPage() {
  const { toast } = useToast();
  const [activeCategory, setActiveCategory] = useState('general');
  const [pendingChanges, setPendingChanges] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);

  // Fetch settings for current category
  const { data: settings, loading, error, refetch } = useFetch<Setting[]>(
    `/api/settings/?category=${activeCategory}`
  );

  // Reset pending changes when category changes
  useEffect(() => {
    setPendingChanges({});
  }, [activeCategory]);

  const handleSettingChange = useCallback((key: string, value: unknown) => {
    setPendingChanges(prev => ({
      ...prev,
      [key]: value,
    }));
  }, []);

  const getDisplayValue = (setting: Setting): unknown => {
    if (setting.key in pendingChanges) {
      return pendingChanges[setting.key];
    }
    return setting.value;
  };

  const hasChanges = Object.keys(pendingChanges).length > 0;

  const saveChanges = async () => {
    if (!hasChanges) return;

    setSaving(true);
    try {
      // Save each changed setting
      for (const [key, value] of Object.entries(pendingChanges)) {
        const response = await fetch(`/api/settings/${key}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ value }),
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || `Failed to save ${key}`);
        }
      }

      toast.success('Settings saved successfully');
      setPendingChanges({});
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const resetSetting = async (key: string) => {
    try {
      const response = await fetch(`/api/settings/${key}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to reset setting');
      }

      toast.success('Setting reset to default');
      // Remove from pending changes if present
      setPendingChanges(prev => {
        const updated = { ...prev };
        delete updated[key];
        return updated;
      });
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to reset setting');
    }
  };

  const discardChanges = () => {
    setPendingChanges({});
    toast.info('Changes discarded');
  };

  const renderSettingControl = (setting: Setting) => {
    const value = getDisplayValue(setting);

    switch (setting.data_type) {
      case 'boolean':
        return (
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={Boolean(value)}
              onChange={e => handleSettingChange(setting.key, e.target.checked)}
              disabled={setting.is_readonly}
            />
            <span className="toggle-slider" />
          </label>
        );

      case 'select':
        return (
          <select
            value={String(value)}
            onChange={e => handleSettingChange(setting.key, e.target.value)}
            disabled={setting.is_readonly}
            className="setting-select"
          >
            {setting.options.map(opt => (
              <option key={String(opt.value)} value={String(opt.value)}>
                {opt.label}
              </option>
            ))}
          </select>
        );

      case 'integer':
      case 'float':
        return (
          <input
            type="number"
            value={value as number}
            onChange={e => handleSettingChange(setting.key, Number(e.target.value))}
            disabled={setting.is_readonly}
            className="setting-input"
            min={setting.validation?.min as number}
            max={setting.validation?.max as number}
          />
        );

      case 'color':
        return (
          <div className="color-input-wrapper">
            <input
              type="color"
              value={value as string}
              onChange={e => handleSettingChange(setting.key, e.target.value)}
              disabled={setting.is_readonly}
              className="setting-color"
            />
            <span className="color-value">{value as string}</span>
          </div>
        );

      case 'string':
      default:
        return (
          <input
            type="text"
            value={value as string}
            onChange={e => handleSettingChange(setting.key, e.target.value)}
            disabled={setting.is_readonly}
            className="setting-input"
          />
        );
    }
  };

  return (
    <div className="settings-page">
      <header className="page-header">
        <div className="page-title">
          <Icon name="Settings" size={28} />
          <div>
            <h1>Settings</h1>
            <p className="page-description">Configure application preferences and behavior</p>
          </div>
        </div>

        {hasChanges && (
          <div className="settings-actions">
            <button
              className="btn btn-secondary"
              onClick={discardChanges}
              disabled={saving}
            >
              Discard
            </button>
            <button
              className="btn btn-primary"
              onClick={saveChanges}
              disabled={saving}
            >
              {saving ? (
                <>
                  <Icon name="Loader2" size={16} className="spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Icon name="Save" size={16} />
                  Save Changes
                </>
              )}
            </button>
          </div>
        )}
      </header>

      <div className="settings-layout">
        {/* Category Sidebar */}
        <nav className="settings-nav">
          {CATEGORIES.map(cat => (
            <button
              key={cat.id}
              className={`nav-item ${activeCategory === cat.id ? 'active' : ''}`}
              onClick={() => setActiveCategory(cat.id)}
            >
              <Icon name={cat.icon} size={20} />
              <div className="nav-content">
                <span className="nav-label">{cat.label}</span>
                <span className="nav-description">{cat.description}</span>
              </div>
            </button>
          ))}
        </nav>

        {/* Settings Content */}
        <main className="settings-content">
          {loading ? (
            <div className="settings-loading">
              <Icon name="Loader2" size={32} className="spin" />
              <span>Loading settings...</span>
            </div>
          ) : error ? (
            <div className="settings-error">
              <Icon name="AlertCircle" size={32} />
              <span>Failed to load settings</span>
              <button className="btn btn-secondary" onClick={() => refetch()}>
                Retry
              </button>
            </div>
          ) : settings && settings.length > 0 ? (
            <div className="settings-list">
              {settings
                .sort((a, b) => a.order - b.order)
                .map(setting => (
                  <div
                    key={setting.key}
                    className={`setting-item ${setting.is_modified || setting.key in pendingChanges ? 'modified' : ''} ${setting.is_readonly ? 'readonly' : ''}`}
                  >
                    <div className="setting-info">
                      <div className="setting-header">
                        <label className="setting-label">{setting.label}</label>
                        {setting.requires_restart && (
                          <span className="restart-badge" title="Requires restart">
                            <Icon name="RefreshCw" size={12} />
                            Restart required
                          </span>
                        )}
                        {setting.is_readonly && (
                          <span className="readonly-badge">
                            <Icon name="Lock" size={12} />
                            Read-only
                          </span>
                        )}
                      </div>
                      <p className="setting-description">{setting.description}</p>
                    </div>
                    <div className="setting-control">
                      {renderSettingControl(setting)}
                      {(setting.is_modified || setting.key in pendingChanges) && !setting.is_readonly && (
                        <button
                          className="reset-btn"
                          onClick={() => resetSetting(setting.key)}
                          title="Reset to default"
                        >
                          <Icon name="RotateCcw" size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <div className="settings-empty">
              <Icon name="Settings2" size={48} />
              <span>No settings in this category</span>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

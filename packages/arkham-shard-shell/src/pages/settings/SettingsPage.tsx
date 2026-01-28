/**
 * SettingsPage - Application settings management
 *
 * Provides UI for viewing and modifying application settings.
 * Settings are organized by category with real-time updates.
 * Includes shard management for enabling/disabling feature modules.
 */

import { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { useToast } from '../../context/ToastContext';
import { useTheme } from '../../context/ThemeContext';
import { useFetch, clearSettingsCache } from '../../hooks';
import { apiDelete, apiPatch, apiPost, apiPut } from '../../utils/api';
import './SettingsPage.css';

// Types
interface SettingOption {
  value: string | number;
  label: string;
  disabled?: boolean;
  disabledReason?: string;
}

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
  options: SettingOption[];
  validation: Record<string, unknown>;
}

interface ShardInfo {
  name: string;
  version: string;
  description: string;
  loaded: boolean;
  enabled: boolean;
  navigation?: {
    category?: string;
    icon?: string;
    label?: string;
  };
  capabilities?: string[];
}

interface CategoryInfo {
  id: string;
  label: string;
  icon: string;
  description: string;
}

interface StorageStats {
  database_connected: boolean;
  database_schemas: string[];
  vector_store_connected: boolean;
  vector_collections: Array<{
    name: string;
    points_count: number;
    vector_size: number;
  }>;
  storage_categories: Record<string, number>;
  total_storage_bytes: number;
}

interface VectorHealthStatus {
  status: string;
  total_vectors: number;
  total_collections: number;
  collections: Array<{
    name: string;
    vector_count: number;
    vector_size: number;
    index_type: string;
    lists: number;
    probes: number;
    last_reindex: string | null;
  }>;
  warnings: string[];
  last_reindex: string | null;
  reindex_in_progress: boolean;
}

// ML Model types
interface ModelInfo {
  id: string;
  name: string;
  model_type: string;
  description: string;
  size_mb: number;
  status: 'installed' | 'not_installed' | 'downloading' | 'error' | 'unknown';
  path: string | null;
  error: string | null;
  required_by: string[];
  is_default: boolean;
  is_selected: boolean;
}

interface ModelsData {
  offline_mode: boolean;
  cache_path: string;
  models: ModelInfo[];
  selected_embedding_model: string | null;
  selected_ocr_model: string | null;
}

// Notification channel types
interface EmailChannelForm {
  name: string;
  smtp_host: string;
  smtp_port: number;
  username: string;
  password: string;
  from_address: string;
  from_name: string;
  use_tls: boolean;
}

interface WebhookChannelForm {
  name: string;
  url: string;
  method: string;
  headers: string; // JSON string for simplicity
  auth_token: string;
  verify_ssl: boolean;
}

const DEFAULT_EMAIL_FORM: EmailChannelForm = {
  name: '',
  smtp_host: '',
  smtp_port: 587,
  username: '',
  password: '',
  from_address: 'noreply@example.com',
  from_name: 'SHATTERED',
  use_tls: true,
};

const DEFAULT_WEBHOOK_FORM: WebhookChannelForm = {
  name: '',
  url: '',
  method: 'POST',
  headers: '{}',
  auth_token: '',
  verify_ssl: true,
};

const CATEGORIES: CategoryInfo[] = [
  { id: 'general', label: 'General', icon: 'Settings', description: 'Language, timezone, and date formats' },
  { id: 'appearance', label: 'Appearance', icon: 'Palette', description: 'Theme, colors, and layout' },
  { id: 'notifications', label: 'Notifications', icon: 'Bell', description: 'Alerts, email, and webhooks' },
  { id: 'performance', label: 'Performance', icon: 'Zap', description: 'Caching and pagination' },
  { id: 'data', label: 'Data', icon: 'Database', description: 'Storage, cleanup, and data management' },
  { id: 'models', label: 'ML Models', icon: 'Brain', description: 'Embedding and OCR model management' },
  { id: 'advanced', label: 'Advanced', icon: 'Wrench', description: 'Developer and debug options' },
  { id: 'shards', label: 'Shards', icon: 'Puzzle', description: 'Enable or disable feature modules' },
];

// Protected shards that cannot be disabled
const PROTECTED_SHARDS = new Set(['dashboard', 'settings']);

export function SettingsPage() {
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const { themePreset, accentColor, setThemePreset, setAccentColor, resetToDefaults } = useTheme();

  // Derive active category from URL path
  const getCategoryFromPath = (path: string): string => {
    const match = path.match(/\/settings\/(\w+)/);
    return match ? match[1] : 'general';
  };

  const [activeCategory, setActiveCategory] = useState(() => getCategoryFromPath(location.pathname));
  const [pendingChanges, setPendingChanges] = useState<Record<string, unknown>>({});
  const [saving, setSaving] = useState(false);
  const [togglingShards, setTogglingShards] = useState<Set<string>>(new Set());
  const [expandedCapabilities, setExpandedCapabilities] = useState<Set<string>>(new Set());

  // Notification channel state
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [showWebhookForm, setShowWebhookForm] = useState(false);
  const [emailForm, setEmailForm] = useState<EmailChannelForm>(DEFAULT_EMAIL_FORM);
  const [webhookForm, setWebhookForm] = useState<WebhookChannelForm>(DEFAULT_WEBHOOK_FORM);
  const [savingChannel, setSavingChannel] = useState(false);
  const [deletingChannel, setDeletingChannel] = useState<string | null>(null);

  // Data management state
  const [dataActionLoading, setDataActionLoading] = useState<string | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState<string | null>(null);

  // Sync activeCategory with URL changes
  useEffect(() => {
    const category = getCategoryFromPath(location.pathname);
    setActiveCategory(category);
  }, [location.pathname]);

  // Navigate when category changes
  const handleCategoryChange = useCallback((categoryId: string) => {
    const newPath = categoryId === 'general' ? '/settings' : `/settings/${categoryId}`;
    navigate(newPath);
  }, [navigate]);

  // Fetch settings for current category (skip for shards category)
  const { data: settings, loading, error, refetch } = useFetch<Setting[]>(
    activeCategory !== 'shards' ? `/api/settings/?category=${activeCategory}` : null
  );

  // Fetch shards list
  const {
    data: shardsData,
    loading: shardsLoading,
    error: shardsError,
    refetch: refetchShards
  } = useFetch<{ shards: ShardInfo[]; count: number }>(
    activeCategory === 'shards' ? '/api/shards/' : null
  );

  // Fetch notification channels
  const {
    data: channelsData,
    loading: channelsLoading,
    error: channelsError,
    refetch: refetchChannels
  } = useFetch<{ channels: string[]; count: number }>(
    activeCategory === 'notifications' ? '/api/notifications/channels' : null
  );

  // Fetch storage stats for data management
  const {
    data: storageStats,
    loading: storageLoading,
    error: storageError,
    refetch: refetchStorageStats
  } = useFetch<StorageStats>(
    activeCategory === 'data' ? '/api/settings/data/stats' : null
  );

  // Fetch ML models for model management
  const {
    data: modelsData,
    loading: modelsLoading,
    error: modelsError,
    refetch: refetchModels
  } = useFetch<ModelsData>(
    activeCategory === 'models' ? '/api/settings/models' : null
  );

  // Model download state
  const [downloadingModel, setDownloadingModel] = useState<string | null>(null);

  // Vector maintenance state
  const [reindexingCollection, setReindexingCollection] = useState<string | null>(null);

  // Fetch vector health for data management
  const {
    data: vectorHealth,
    loading: vectorHealthLoading,
    refetch: refetchVectorHealth
  } = useFetch<VectorHealthStatus>(
    activeCategory === 'data' ? '/api/settings/vectors/health' : null
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
        await apiPut(`/api/settings/${key}`, { value });
      }

      toast.success('Settings saved successfully');
      setPendingChanges({});
      clearSettingsCache(); // Clear cached settings so useSettings refetches
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const resetSetting = async (key: string) => {
    try {
      await apiDelete(`/api/settings/${key}`);

      toast.success('Setting reset to default');
      // Remove from pending changes if present
      setPendingChanges(prev => {
        const updated = { ...prev };
        delete updated[key];
        return updated;
      });
      clearSettingsCache(); // Clear cached settings so useSettings refetches
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to reset setting');
    }
  };

  const discardChanges = () => {
    setPendingChanges({});
    toast.info('Changes discarded');
  };

  // Toggle shard enabled state
  const toggleShard = async (shardName: string, enable: boolean) => {
    if (PROTECTED_SHARDS.has(shardName)) {
      toast.error(`Cannot disable protected shard: ${shardName}`);
      return;
    }

    setTogglingShards(prev => new Set(prev).add(shardName));

    try {
      const result = await apiPatch<{ message?: string }>(`/api/shards/${shardName}`, { enabled: enable });
      toast.success(result.message || `Shard ${enable ? 'enabled' : 'disabled'} successfully`);
      refetchShards();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update shard');
    } finally {
      setTogglingShards(prev => {
        const next = new Set(prev);
        next.delete(shardName);
        return next;
      });
    }
  };

  // Save email channel
  const saveEmailChannel = async () => {
    if (!emailForm.name || !emailForm.smtp_host) {
      toast.error('Channel name and SMTP host are required');
      return;
    }

    setSavingChannel(true);
    try {
      await apiPost('/api/notifications/channels/email', {
        name: emailForm.name,
        smtp_host: emailForm.smtp_host,
        smtp_port: emailForm.smtp_port,
        username: emailForm.username || null,
        password: emailForm.password || null,
        from_address: emailForm.from_address,
        from_name: emailForm.from_name,
        use_tls: emailForm.use_tls,
      });

      toast.success(`Email channel "${emailForm.name}" configured`);
      setShowEmailForm(false);
      setEmailForm(DEFAULT_EMAIL_FORM);
      refetchChannels();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save channel');
    } finally {
      setSavingChannel(false);
    }
  };

  // Save webhook channel
  const saveWebhookChannel = async () => {
    if (!webhookForm.name || !webhookForm.url) {
      toast.error('Channel name and URL are required');
      return;
    }

    // Validate URL
    try {
      new URL(webhookForm.url);
    } catch {
      toast.error('Invalid webhook URL');
      return;
    }

    // Validate headers JSON
    let headers: Record<string, string> = {};
    try {
      headers = JSON.parse(webhookForm.headers || '{}');
    } catch {
      toast.error('Invalid headers JSON');
      return;
    }

    setSavingChannel(true);
    try {
      await apiPost('/api/notifications/channels/webhook', {
        name: webhookForm.name,
        url: webhookForm.url,
        method: webhookForm.method,
        headers: Object.keys(headers).length > 0 ? headers : null,
        auth_token: webhookForm.auth_token || null,
        verify_ssl: webhookForm.verify_ssl,
      });

      toast.success(`Webhook channel "${webhookForm.name}" configured`);
      setShowWebhookForm(false);
      setWebhookForm(DEFAULT_WEBHOOK_FORM);
      refetchChannels();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save channel');
    } finally {
      setSavingChannel(false);
    }
  };

  // Delete channel
  const deleteChannel = async (channelName: string) => {
    if (channelName === 'log') {
      toast.error('Cannot remove the default log channel');
      return;
    }

    setDeletingChannel(channelName);
    try {
      await apiDelete(`/api/notifications/channels/${channelName}`);

      toast.success(`Channel "${channelName}" removed`);
      refetchChannels();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove channel');
    } finally {
      setDeletingChannel(null);
    }
  };

  // Data management actions
  const executeDataAction = async (action: string) => {
    setDataActionLoading(action);
    setShowConfirmDialog(null);

    try {
      const result = await apiPost<{ message: string }>(`/api/settings/data/${action}`);
      toast.success(result.message);
      refetchStorageStats();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : `Failed to execute ${action}`);
    } finally {
      setDataActionLoading(null);
    }
  };

  const clearLocalStorage = () => {
    try {
      localStorage.clear();
      toast.success('Local storage cleared');
    } catch {
      toast.error('Failed to clear local storage');
    }
  };

  // Download ML model
  const downloadModel = async (modelId: string) => {
    setDownloadingModel(modelId);
    try {
      const result = await apiPost<{ message?: string }>(`/api/settings/models/${modelId}/download`);
      toast.success(result.message || `Model ${modelId} downloaded successfully`);
      refetchModels();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to download model');
    } finally {
      setDownloadingModel(null);
    }
  };

  // Reindex vector collection
  const triggerReindex = async (collectionName?: string) => {
    const endpoint = collectionName
      ? `/api/settings/vectors/reindex/${collectionName}`
      : '/api/settings/vectors/reindex';

    setReindexingCollection(collectionName || 'all');
    try {
      const result = await apiPost<{ message?: string }>(endpoint);
      toast.success(result.message || 'Reindex completed successfully');
      refetchVectorHealth();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to reindex');
    } finally {
      setReindexingCollection(null);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Group shards by navigation category
  const groupShardsByCategory = (shards: ShardInfo[]) => {
    const groups: Record<string, ShardInfo[]> = {};
    for (const shard of shards) {
      const category = shard.navigation?.category || 'Other';
      if (!groups[category]) groups[category] = [];
      groups[category].push(shard);
    }
    return groups;
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

      case 'select': {
        // Find the original typed value from options when selection changes
        const handleSelectChange = (selectedValue: string) => {
          const option = setting.options.find(opt => String(opt.value) === selectedValue);
          // Prevent selection of disabled options
          if (option?.disabled) {
            return;
          }
          // Use the original typed value from the option, not the string
          handleSettingChange(setting.key, option ? option.value : selectedValue);
        };

        // Check if any option is disabled (for showing tooltip info)
        const hasDisabledOptions = setting.options.some(opt => opt.disabled);
        const selectedOption = setting.options.find(opt => String(opt.value) === String(value));
        const isCloudOption = selectedOption?.label?.includes('[CLOUD API]');

        return (
          <div className="select-wrapper">
            <select
              value={String(value)}
              onChange={e => handleSelectChange(e.target.value)}
              disabled={setting.is_readonly}
              className={`setting-select ${isCloudOption ? 'cloud-option' : ''}`}
            >
              {setting.options.map(opt => (
                <option
                  key={String(opt.value)}
                  value={String(opt.value)}
                  disabled={opt.disabled}
                  title={opt.disabledReason}
                >
                  {opt.label}{opt.disabled ? ' (unavailable)' : ''}
                </option>
              ))}
            </select>
            {isCloudOption && (
              <div className="cloud-warning">
                <Icon name="Cloud" size={14} />
                <span>Data will be sent to external API</span>
              </div>
            )}
            {hasDisabledOptions && !isCloudOption && (
              <div className="disabled-options-hint">
                <Icon name="Info" size={12} />
                <span>Some options require API key configuration</span>
              </div>
            )}
          </div>
        );
      }

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
              onClick={() => handleCategoryChange(cat.id)}
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
          {activeCategory === 'appearance' ? (
            // Custom Appearance UI
            <div className="appearance-settings">
              <div className="appearance-header">
                <p className="appearance-description">
                  Customize the look and feel of the application. Changes are applied immediately.
                </p>
              </div>

              {/* Theme Selection */}
              <section className="appearance-section">
                <h3 className="section-title">
                  <Icon name="Palette" size={18} />
                  Theme
                </h3>
                <div className="theme-grid">
                  <button
                    className={`theme-card ${themePreset === 'arkham' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('arkham')}
                  >
                    <div className="theme-preview theme-preview-arkham">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Arkham</span>
                      <span className="theme-desc">Dark cyberpunk theme</span>
                    </div>
                    {themePreset === 'arkham' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'newsroom' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('newsroom')}
                  >
                    <div className="theme-preview theme-preview-newsroom">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Newsroom</span>
                      <span className="theme-desc">Light parchment</span>
                    </div>
                    {themePreset === 'newsroom' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'ocean' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('ocean')}
                  >
                    <div className="theme-preview theme-preview-ocean">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Ocean</span>
                      <span className="theme-desc">Deep blue dark</span>
                    </div>
                    {themePreset === 'ocean' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'forest' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('forest')}
                  >
                    <div className="theme-preview theme-preview-forest">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Forest</span>
                      <span className="theme-desc">Nature dark</span>
                    </div>
                    {themePreset === 'forest' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'frost' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('frost')}
                  >
                    <div className="theme-preview theme-preview-frost">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Frost</span>
                      <span className="theme-desc">Cool light</span>
                    </div>
                    {themePreset === 'frost' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'midnight' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('midnight')}
                  >
                    <div className="theme-preview theme-preview-midnight">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Midnight</span>
                      <span className="theme-desc">Pure OLED dark</span>
                    </div>
                    {themePreset === 'midnight' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'terminal' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('terminal')}
                  >
                    <div className="theme-preview theme-preview-terminal">
                      <div className="preview-sidebar" />
                      <div className="preview-content">
                        <div className="preview-header" />
                        <div className="preview-body" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">Terminal</span>
                      <span className="theme-desc">Hacker green</span>
                    </div>
                    {themePreset === 'terminal' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>

                  <button
                    className={`theme-card ${themePreset === 'system' ? 'selected' : ''}`}
                    onClick={() => setThemePreset('system')}
                  >
                    <div className="theme-preview theme-preview-system">
                      <div className="preview-split">
                        <div className="preview-dark" />
                        <div className="preview-light" />
                      </div>
                    </div>
                    <div className="theme-info">
                      <span className="theme-name">System</span>
                      <span className="theme-desc">Follow OS preference</span>
                    </div>
                    {themePreset === 'system' && (
                      <Icon name="Check" size={16} className="theme-check" />
                    )}
                  </button>
                </div>
              </section>

              {/* Accent Color */}
              <section className="appearance-section">
                <h3 className="section-title">
                  <Icon name="Pipette" size={18} />
                  Accent Color
                </h3>
                <p className="section-description">
                  Choose a primary accent color for buttons, links, and highlights.
                </p>
                <div className="accent-picker">
                  <div className="accent-presets">
                    {[
                      { color: '#e94560', name: 'Ruby' },
                      { color: '#3b82f6', name: 'Blue' },
                      { color: '#10b981', name: 'Emerald' },
                      { color: '#f59e0b', name: 'Amber' },
                      { color: '#8b5cf6', name: 'Violet' },
                      { color: '#ec4899', name: 'Pink' },
                      { color: '#06b6d4', name: 'Cyan' },
                      { color: '#84cc16', name: 'Lime' },
                    ].map(preset => (
                      <button
                        key={preset.color}
                        className={`accent-preset ${accentColor === preset.color ? 'selected' : ''}`}
                        style={{ backgroundColor: preset.color }}
                        onClick={() => setAccentColor(preset.color)}
                        title={preset.name}
                      >
                        {accentColor === preset.color && (
                          <Icon name="Check" size={14} />
                        )}
                      </button>
                    ))}
                  </div>
                  <div className="accent-custom">
                    <label className="accent-label">Custom color:</label>
                    <div className="color-input-wrapper">
                      <input
                        type="color"
                        value={accentColor}
                        onChange={e => setAccentColor(e.target.value)}
                        className="setting-color"
                      />
                      <span className="color-value">{accentColor.toUpperCase()}</span>
                    </div>
                  </div>
                </div>
              </section>

              {/* Reset to Defaults */}
              <section className="appearance-section appearance-reset">
                <h3 className="section-title">
                  <Icon name="RotateCcw" size={18} />
                  Reset Appearance
                </h3>
                <p className="section-description">
                  Restore all appearance settings to their default values (Arkham theme with Ruby accent).
                </p>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    resetToDefaults();
                    toast.success('Appearance reset to defaults');
                  }}
                >
                  <Icon name="RotateCcw" size={16} />
                  Reset to Defaults
                </button>
              </section>
            </div>
          ) : activeCategory === 'data' ? (
            // Custom Data Management UI
            <div className="data-settings">
              <div className="data-header">
                <p className="data-description">
                  Manage application data, clear caches, and perform maintenance tasks.
                  Destructive actions require confirmation.
                </p>
              </div>

              {/* Storage Overview */}
              <section className="data-section">
                <h3 className="section-title">
                  <Icon name="HardDrive" size={18} />
                  Storage Overview
                </h3>
                {storageLoading ? (
                  <div className="section-loading">
                    <Icon name="Loader2" size={20} className="spin" />
                    <span>Loading storage info...</span>
                  </div>
                ) : storageError ? (
                  <div className="section-error">
                    <span>Failed to load storage info</span>
                    <button className="btn btn-sm" onClick={() => refetchStorageStats()}>Retry</button>
                  </div>
                ) : storageStats ? (
                  <div className="storage-overview">
                    <div className="storage-stat-grid">
                      <div className={`storage-stat ${storageStats.database_connected ? 'connected' : 'disconnected'}`}>
                        <Icon name="Database" size={20} />
                        <div className="stat-info">
                          <span className="stat-label">Database</span>
                          <span className="stat-value">
                            {storageStats.database_connected ? 'Connected' : 'Disconnected'}
                          </span>
                          {storageStats.database_schemas.length > 0 && (
                            <span className="stat-detail">{storageStats.database_schemas.length} schema(s)</span>
                          )}
                        </div>
                      </div>
                      <div className={`storage-stat ${storageStats.vector_store_connected ? 'connected' : 'disconnected'}`}>
                        <Icon name="Cpu" size={20} />
                        <div className="stat-info">
                          <span className="stat-label">Vector Store</span>
                          <span className="stat-value">
                            {storageStats.vector_store_connected ? 'Connected' : 'Disconnected'}
                          </span>
                          {storageStats.vector_collections.length > 0 && (
                            <span className="stat-detail">
                              {storageStats.vector_collections.reduce((sum, c) => sum + c.points_count, 0).toLocaleString()} vectors
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="storage-stat">
                        <Icon name="Folder" size={20} />
                        <div className="stat-info">
                          <span className="stat-label">File Storage</span>
                          <span className="stat-value">{formatBytes(storageStats.total_storage_bytes)}</span>
                          {Object.keys(storageStats.storage_categories).length > 0 && (
                            <span className="stat-detail">
                              {Object.keys(storageStats.storage_categories).length} categories
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="storage-stat">
                        <Icon name="Archive" size={20} />
                        <div className="stat-info">
                          <span className="stat-label">Local Storage</span>
                          <span className="stat-value">Browser</span>
                          <span className="stat-detail">Preferences &amp; cache</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </section>

              {/* Data Settings */}
              <section className="data-section">
                <h3 className="section-title">
                  <Icon name="Settings2" size={18} />
                  Data Retention
                </h3>
                {loading ? (
                  <div className="section-loading">
                    <Icon name="Loader2" size={20} className="spin" />
                    <span>Loading settings...</span>
                  </div>
                ) : settings && settings.length > 0 ? (
                  <div className="settings-list compact">
                    {settings
                      .sort((a, b) => a.order - b.order)
                      .map(setting => (
                        <div
                          key={setting.key}
                          className={`setting-item ${setting.is_modified || setting.key in pendingChanges ? 'modified' : ''}`}
                        >
                          <div className="setting-info">
                            <label className="setting-label">{setting.label}</label>
                            <p className="setting-description">{setting.description}</p>
                          </div>
                          <div className="setting-control">
                            {renderSettingControl(setting)}
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <p className="no-settings">No data settings available</p>
                )}
              </section>

              {/* Cleanup Actions */}
              <section className="data-section data-actions">
                <h3 className="section-title">
                  <Icon name="Trash2" size={18} />
                  Cleanup Actions
                </h3>
                <p className="section-description">
                  Clear cached data and temporary files. These actions cannot be undone.
                </p>

                <div className="action-cards">
                  <div className="action-card">
                    <div className="action-icon">
                      <Icon name="Archive" size={24} />
                    </div>
                    <div className="action-info">
                      <span className="action-title">Clear Local Storage</span>
                      <span className="action-desc">Remove cached preferences and UI state from browser</span>
                    </div>
                    <button
                      className="btn btn-secondary"
                      onClick={clearLocalStorage}
                    >
                      <Icon name="Trash2" size={16} />
                      Clear
                    </button>
                  </div>

                  <div className="action-card">
                    <div className="action-icon">
                      <Icon name="FileX" size={24} />
                    </div>
                    <div className="action-info">
                      <span className="action-title">Clear Temp Files</span>
                      <span className="action-desc">Remove temporary processing files</span>
                    </div>
                    <button
                      className="btn btn-secondary"
                      onClick={() => executeDataAction('clear-temp')}
                      disabled={dataActionLoading !== null}
                    >
                      {dataActionLoading === 'clear-temp' ? (
                        <Icon name="Loader2" size={16} className="spin" />
                      ) : (
                        <Icon name="Trash2" size={16} />
                      )}
                      Clear
                    </button>
                  </div>

                  <div className="action-card warning">
                    <div className="action-icon">
                      <Icon name="Cpu" size={24} />
                    </div>
                    <div className="action-info">
                      <span className="action-title">Clear Vector Embeddings</span>
                      <span className="action-desc">Remove all semantic search indexes. Will require re-embedding.</span>
                    </div>
                    <button
                      className="btn btn-warning"
                      onClick={() => setShowConfirmDialog('clear-vectors')}
                      disabled={dataActionLoading !== null}
                    >
                      {dataActionLoading === 'clear-vectors' ? (
                        <Icon name="Loader2" size={16} className="spin" />
                      ) : (
                        <Icon name="Trash2" size={16} />
                      )}
                      Clear
                    </button>
                  </div>

                  <div className="action-card warning">
                    <div className="action-icon">
                      <Icon name="Database" size={24} />
                    </div>
                    <div className="action-info">
                      <span className="action-title">Clear Database</span>
                      <span className="action-desc">Remove all documents, entities, and analysis data. Settings are preserved.</span>
                    </div>
                    <button
                      className="btn btn-warning"
                      onClick={() => setShowConfirmDialog('clear-database')}
                      disabled={dataActionLoading !== null}
                    >
                      {dataActionLoading === 'clear-database' ? (
                        <Icon name="Loader2" size={16} className="spin" />
                      ) : (
                        <Icon name="Trash2" size={16} />
                      )}
                      Clear
                    </button>
                  </div>

                  <div className="action-card danger">
                    <div className="action-icon">
                      <Icon name="AlertTriangle" size={24} />
                    </div>
                    <div className="action-info">
                      <span className="action-title">Reset All Data</span>
                      <span className="action-desc">Clear database, vectors, and temp files. Complete fresh start.</span>
                    </div>
                    <button
                      className="btn btn-danger"
                      onClick={() => setShowConfirmDialog('reset-all')}
                      disabled={dataActionLoading !== null}
                    >
                      {dataActionLoading === 'reset-all' ? (
                        <Icon name="Loader2" size={16} className="spin" />
                      ) : (
                        <Icon name="RotateCcw" size={16} />
                      )}
                      Reset All
                    </button>
                  </div>
                </div>
              </section>

              {/* Export/Import Section */}
              <section className="data-section">
                <h3 className="section-title">
                  <Icon name="Download" size={18} />
                  Export Settings
                </h3>
                <p className="section-description">
                  Export your settings for backup or to transfer to another instance.
                </p>
                <div className="export-actions">
                  <a
                    href="/api/settings/export"
                    className="btn btn-secondary"
                    download="shattered-settings.json"
                  >
                    <Icon name="Download" size={16} />
                    Export Settings JSON
                  </a>
                </div>
              </section>

              {/* Vector Maintenance Section */}
              <section className="data-section">
                <h3 className="section-title">
                  <Icon name="Cpu" size={18} />
                  Vector Index Maintenance
                </h3>
                <p className="section-description">
                  Rebuild IVFFlat indexes after significant data changes. This optimizes search performance
                  by recalculating index parameters based on current data distribution.
                </p>

                {vectorHealthLoading ? (
                  <div className="section-loading">
                    <Icon name="Loader2" size={20} className="spin" />
                    <span>Loading vector health...</span>
                  </div>
                ) : vectorHealth ? (
                  <div className="vector-maintenance">
                    {/* Status Overview */}
                    <div className="vector-status-bar">
                      <div className={`status-indicator ${vectorHealth.status}`}>
                        <Icon name={vectorHealth.status === 'healthy' ? 'CheckCircle' : 'AlertCircle'} size={16} />
                        <span>{vectorHealth.status === 'healthy' ? 'Healthy' : vectorHealth.status}</span>
                      </div>
                      <span className="status-detail">
                        {vectorHealth.total_vectors.toLocaleString()} vectors in {vectorHealth.total_collections} collection(s)
                      </span>
                      {vectorHealth.last_reindex && (
                        <span className="last-reindex">
                          Last reindex: {new Date(vectorHealth.last_reindex).toLocaleString()}
                        </span>
                      )}
                    </div>

                    {/* Warnings */}
                    {vectorHealth.warnings.length > 0 && (
                      <div className="vector-warnings">
                        {vectorHealth.warnings.map((warning, i) => (
                          <div key={i} className="warning-item">
                            <Icon name="AlertTriangle" size={14} />
                            <span>{warning}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Collections Table */}
                    {vectorHealth.collections.length > 0 && (
                      <div className="collections-table">
                        <div className="table-header">
                          <span className="col-name">Collection</span>
                          <span className="col-vectors">Vectors</span>
                          <span className="col-index">Index</span>
                          <span className="col-params">Params</span>
                          <span className="col-action">Action</span>
                        </div>
                        {vectorHealth.collections.map(coll => (
                          <div key={coll.name} className="table-row">
                            <span className="col-name" title={coll.name}>{coll.name}</span>
                            <span className="col-vectors">{coll.vector_count.toLocaleString()}</span>
                            <span className="col-index">{coll.index_type}</span>
                            <span className="col-params">
                              lists={coll.lists}, probes={coll.probes}
                            </span>
                            <span className="col-action">
                              <button
                                className="btn btn-sm btn-secondary"
                                onClick={() => triggerReindex(coll.name)}
                                disabled={reindexingCollection !== null}
                                title="Reindex this collection"
                              >
                                {reindexingCollection === coll.name ? (
                                  <Icon name="Loader2" size={14} className="spin" />
                                ) : (
                                  <Icon name="RefreshCw" size={14} />
                                )}
                              </button>
                            </span>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Reindex All Button */}
                    <div className="reindex-actions">
                      <button
                        className="btn btn-primary"
                        onClick={() => triggerReindex()}
                        disabled={reindexingCollection !== null || vectorHealth.reindex_in_progress}
                      >
                        {reindexingCollection === 'all' || vectorHealth.reindex_in_progress ? (
                          <>
                            <Icon name="Loader2" size={16} className="spin" />
                            Reindexing...
                          </>
                        ) : (
                          <>
                            <Icon name="RefreshCw" size={16} />
                            Reindex All Collections
                          </>
                        )}
                      </button>
                      <span className="reindex-hint">
                        Rebuilds all IVFFlat indexes with optimal parameters
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="section-error">
                    <span>Vector service not available</span>
                  </div>
                )}
              </section>

              {/* Confirmation Dialog */}
              {showConfirmDialog && (
                <div className="confirm-dialog-overlay" onClick={() => setShowConfirmDialog(null)}>
                  <div className="confirm-dialog" onClick={e => e.stopPropagation()}>
                    <div className="confirm-icon">
                      <Icon name="AlertTriangle" size={32} />
                    </div>
                    <h4 className="confirm-title">
                      {showConfirmDialog === 'reset-all'
                        ? 'Reset All Data?'
                        : showConfirmDialog === 'clear-database'
                        ? 'Clear Database?'
                        : 'Clear Vector Embeddings?'}
                    </h4>
                    <p className="confirm-message">
                      {showConfirmDialog === 'reset-all'
                        ? 'This will permanently delete all documents, entities, analysis data, and vector embeddings. Your settings will be preserved. This action cannot be undone.'
                        : showConfirmDialog === 'clear-database'
                        ? 'This will permanently delete all documents, entities, and analysis data. Your settings will be preserved. This action cannot be undone.'
                        : 'This will delete all vector embeddings. You will need to re-embed your documents to use semantic search. This action cannot be undone.'}
                    </p>
                    <div className="confirm-actions">
                      <button
                        className="btn btn-secondary"
                        onClick={() => setShowConfirmDialog(null)}
                      >
                        Cancel
                      </button>
                      <button
                        className={`btn ${showConfirmDialog === 'reset-all' ? 'btn-danger' : 'btn-warning'}`}
                        onClick={() => executeDataAction(showConfirmDialog)}
                      >
                        {showConfirmDialog === 'reset-all' ? 'Yes, Reset Everything' : 'Yes, Clear Data'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : activeCategory === 'models' ? (
            // ML Models Management UI
            <div className="models-settings">
              <div className="models-header">
                <p className="models-description">
                  Manage ML models for embeddings and OCR. Download models on-demand or pre-cache them for air-gapped deployments.
                </p>
                {modelsData?.offline_mode && (
                  <div className="offline-mode-banner">
                    <Icon name="WifiOff" size={16} />
                    <span>Offline Mode Enabled - Downloads are disabled. Pre-cache models before deployment.</span>
                  </div>
                )}
              </div>

              {modelsLoading ? (
                <div className="section-loading">
                  <Icon name="Loader2" size={20} className="spin" />
                  <span>Loading models...</span>
                </div>
              ) : modelsError ? (
                <div className="section-error">
                  <span>Failed to load models</span>
                  <button className="btn btn-sm" onClick={() => refetchModels()}>Retry</button>
                </div>
              ) : modelsData ? (
                <>
                  {/* Embedding Models */}
                  <section className="models-section">
                    <h3 className="section-title">
                      <Icon name="FileText" size={18} />
                      Embedding Models
                    </h3>
                    <p className="section-description">
                      Used for semantic search and document similarity. Required by the Embed shard.
                    </p>
                    <div className="models-list">
                      {modelsData.models
                        .filter(m => m.model_type === 'embedding')
                        .map(model => (
                          <div key={model.id} className={`model-item ${model.status} ${model.is_selected ? 'selected' : ''}`}>
                            <div className="model-icon">
                              <Icon name={model.is_selected ? 'CheckCircle2' : model.status === 'installed' ? 'CheckCircle' : 'Circle'} size={20} />
                            </div>
                            <div className="model-info">
                              <div className="model-header">
                                <span className="model-name">{model.name}</span>
                                {model.is_selected && <span className="selected-badge">Selected</span>}
                                {model.is_default && !model.is_selected && <span className="default-badge">Default</span>}
                                <span className="model-size">{model.size_mb} MB</span>
                              </div>
                              <p className="model-description">{model.description}</p>
                              {model.path && (
                                <span className="model-path" title={model.path}>
                                  <Icon name="Folder" size={12} />
                                  Cached locally
                                </span>
                              )}
                            </div>
                            <div className="model-action">
                              {model.status === 'installed' ? (
                                <span className="status-badge installed">
                                  <Icon name="Check" size={14} />
                                  Installed
                                </span>
                              ) : model.status === 'downloading' || downloadingModel === model.id ? (
                                <span className="status-badge downloading">
                                  <Icon name="Loader2" size={14} className="spin" />
                                  Downloading...
                                </span>
                              ) : (
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => downloadModel(model.id)}
                                  disabled={modelsData.offline_mode || downloadingModel !== null}
                                  title={modelsData.offline_mode ? 'Downloads disabled in offline mode' : 'Download model'}
                                >
                                  <Icon name="Download" size={14} />
                                  Download
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </section>

                  {/* OCR Models */}
                  <section className="models-section">
                    <h3 className="section-title">
                      <Icon name="ScanText" size={18} />
                      OCR Models
                    </h3>
                    <p className="section-description">
                      Used for text extraction from images. Required by the OCR shard.
                    </p>
                    <div className="models-list">
                      {modelsData.models
                        .filter(m => m.model_type === 'ocr')
                        .map(model => (
                          <div key={model.id} className={`model-item ${model.status} ${model.is_selected ? 'selected' : ''}`}>
                            <div className="model-icon">
                              <Icon name={model.is_selected ? 'CheckCircle2' : model.status === 'installed' ? 'CheckCircle' : 'Circle'} size={20} />
                            </div>
                            <div className="model-info">
                              <div className="model-header">
                                <span className="model-name">{model.name}</span>
                                {model.is_selected && <span className="selected-badge">Selected</span>}
                                {model.is_default && !model.is_selected && <span className="default-badge">Default</span>}
                                <span className="model-size">{model.size_mb} MB</span>
                              </div>
                              <p className="model-description">{model.description}</p>
                              {model.path && (
                                <span className="model-path" title={model.path}>
                                  <Icon name="Folder" size={12} />
                                  Cached locally
                                </span>
                              )}
                            </div>
                            <div className="model-action">
                              {model.status === 'installed' ? (
                                <span className="status-badge installed">
                                  <Icon name="Check" size={14} />
                                  Installed
                                </span>
                              ) : model.status === 'downloading' || downloadingModel === model.id ? (
                                <span className="status-badge downloading">
                                  <Icon name="Loader2" size={14} className="spin" />
                                  Downloading...
                                </span>
                              ) : (
                                <button
                                  className="btn btn-secondary btn-sm"
                                  onClick={() => downloadModel(model.id)}
                                  disabled={modelsData.offline_mode || downloadingModel !== null}
                                  title={modelsData.offline_mode ? 'Downloads disabled in offline mode' : 'Download model'}
                                >
                                  <Icon name="Download" size={14} />
                                  Download
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </section>

                  {/* Air-Gap Info */}
                  <section className="models-section models-info">
                    <h3 className="section-title">
                      <Icon name="Shield" size={18} />
                      Air-Gap Deployment
                    </h3>
                    <div className="info-box">
                      <p>
                        <strong>SHATTERED is 100% air-gap capable</strong> when configured correctly. Follow these steps:
                      </p>

                      <h4>1. Pre-cache ML Models</h4>
                      <ol>
                        <li>Download required embedding models on a connected machine using the buttons above</li>
                        <li>Models are cached in: <code>{modelsData.cache_path || '~/.cache/huggingface/hub'}</code></li>
                        <li>Copy the entire cache directory to your air-gapped system</li>
                        <li>Set environment variable: <code>ARKHAM_OFFLINE_MODE=true</code></li>
                        <li>Optionally set <code>ARKHAM_MODEL_CACHE=/path/to/cache</code> for custom location</li>
                      </ol>

                      <h4>2. Local LLM Setup</h4>
                      <p>Configure a local LLM endpoint (LM Studio, Ollama, or vLLM):</p>
                      <ul>
                        <li>LM Studio: <code>http://localhost:1234/v1</code></li>
                        <li>Ollama: <code>http://localhost:11434/v1</code></li>
                        <li>vLLM: <code>http://localhost:8000/v1</code></li>
                      </ul>

                      <h4>3. Geographic Visualization (Optional)</h4>
                      <p style={{ color: 'var(--warning-color)' }}>
                        <Icon name="AlertTriangle" size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '4px' }} />
                        The <strong>Geo View</strong> tab in the Graph page requires internet access for map tiles from OpenStreetMap.
                      </p>
                      <p>To disable geographic features for full air-gap operation:</p>
                      <ul>
                        <li>Simply avoid using the "Geo View" tab - all other graph views work offline</li>
                        <li>For advanced users: set up a local tile server with offline OpenStreetMap data</li>
                      </ul>

                      <h4>4. Environment Variables Summary</h4>
                      <pre style={{ background: 'var(--bg-tertiary)', padding: '0.75rem', borderRadius: '4px', fontSize: '0.75rem', overflow: 'auto' }}>
{`# Required for air-gap
ARKHAM_OFFLINE_MODE=true
DATABASE_URL=postgresql://user:pass@localhost:5432/shattered

# Local LLM (choose one)
LLM_ENDPOINT=http://localhost:1234/v1

# Optional: custom model cache
ARKHAM_MODEL_CACHE=/path/to/cache`}
                      </pre>
                    </div>
                  </section>
                </>
              ) : null}
            </div>
          ) : activeCategory === 'notifications' ? (
            // Custom Notifications UI
            <div className="notifications-settings">
              <div className="notifications-header">
                <p className="notifications-description">
                  Configure how you receive alerts and notifications. Add email or webhook channels for external delivery.
                </p>
              </div>

              {/* Basic Notification Settings */}
              <section className="notifications-section">
                <h3 className="section-title">
                  <Icon name="Bell" size={18} />
                  General Settings
                </h3>
                {loading ? (
                  <div className="section-loading">
                    <Icon name="Loader2" size={20} className="spin" />
                    <span>Loading settings...</span>
                  </div>
                ) : error ? (
                  <div className="section-error">
                    <span>Failed to load settings</span>
                    <button className="btn btn-sm" onClick={() => refetch()}>Retry</button>
                  </div>
                ) : settings && settings.length > 0 ? (
                  <div className="settings-list compact">
                    {settings
                      .sort((a, b) => a.order - b.order)
                      .map(setting => (
                        <div
                          key={setting.key}
                          className={`setting-item ${setting.is_modified || setting.key in pendingChanges ? 'modified' : ''}`}
                        >
                          <div className="setting-info">
                            <label className="setting-label">{setting.label}</label>
                            <p className="setting-description">{setting.description}</p>
                          </div>
                          <div className="setting-control">
                            {renderSettingControl(setting)}
                          </div>
                        </div>
                      ))}
                  </div>
                ) : (
                  <p className="no-settings">No notification settings available</p>
                )}
              </section>

              {/* Notification Channels */}
              <section className="notifications-section">
                <h3 className="section-title">
                  <Icon name="Radio" size={18} />
                  Delivery Channels
                </h3>
                <p className="section-description">
                  Configure where notifications are sent. The log channel is always active for in-app notifications.
                </p>

                {channelsLoading ? (
                  <div className="section-loading">
                    <Icon name="Loader2" size={20} className="spin" />
                    <span>Loading channels...</span>
                  </div>
                ) : channelsError ? (
                  <div className="section-error">
                    <span>Failed to load channels</span>
                    <button className="btn btn-sm" onClick={() => refetchChannels()}>Retry</button>
                  </div>
                ) : (
                  <div className="channels-list">
                    {channelsData?.channels.map(channel => (
                      <div key={channel} className="channel-item">
                        <div className="channel-icon">
                          <Icon
                            name={channel === 'log' ? 'FileText' : channel.includes('email') ? 'Mail' : 'Webhook'}
                            size={20}
                          />
                        </div>
                        <div className="channel-info">
                          <span className="channel-name">{channel}</span>
                          <span className="channel-type">
                            {channel === 'log' ? 'In-app logging' :
                             channel.includes('email') ? 'Email (SMTP)' : 'Webhook'}
                          </span>
                        </div>
                        {channel !== 'log' && (
                          <button
                            className="btn btn-icon btn-danger-subtle"
                            onClick={() => deleteChannel(channel)}
                            disabled={deletingChannel === channel}
                            title="Remove channel"
                          >
                            {deletingChannel === channel ? (
                              <Icon name="Loader2" size={16} className="spin" />
                            ) : (
                              <Icon name="Trash2" size={16} />
                            )}
                          </button>
                        )}
                        {channel === 'log' && (
                          <span className="channel-badge">Default</span>
                        )}
                      </div>
                    ))}

                    {(!channelsData?.channels || channelsData.channels.length === 0) && (
                      <p className="no-channels">No channels configured</p>
                    )}
                  </div>
                )}

                {/* Add Channel Buttons */}
                <div className="channel-actions">
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowEmailForm(true);
                      setShowWebhookForm(false);
                    }}
                  >
                    <Icon name="Mail" size={16} />
                    Add Email Channel
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => {
                      setShowWebhookForm(true);
                      setShowEmailForm(false);
                    }}
                  >
                    <Icon name="Webhook" size={16} />
                    Add Webhook Channel
                  </button>
                </div>
              </section>

              {/* Email Channel Form */}
              {showEmailForm && (
                <section className="notifications-section channel-form">
                  <h3 className="section-title">
                    <Icon name="Mail" size={18} />
                    Configure Email Channel
                  </h3>
                  <div className="form-grid">
                    <div className="form-group">
                      <label>Channel Name *</label>
                      <input
                        type="text"
                        value={emailForm.name}
                        onChange={e => setEmailForm(prev => ({ ...prev, name: e.target.value }))}
                        placeholder="e.g., primary-email"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>SMTP Host *</label>
                      <input
                        type="text"
                        value={emailForm.smtp_host}
                        onChange={e => setEmailForm(prev => ({ ...prev, smtp_host: e.target.value }))}
                        placeholder="e.g., smtp.gmail.com"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>SMTP Port</label>
                      <input
                        type="number"
                        value={emailForm.smtp_port}
                        onChange={e => setEmailForm(prev => ({ ...prev, smtp_port: parseInt(e.target.value) || 587 }))}
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>Username</label>
                      <input
                        type="text"
                        value={emailForm.username}
                        onChange={e => setEmailForm(prev => ({ ...prev, username: e.target.value }))}
                        placeholder="SMTP username"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>Password</label>
                      <input
                        type="password"
                        value={emailForm.password}
                        onChange={e => setEmailForm(prev => ({ ...prev, password: e.target.value }))}
                        placeholder="SMTP password"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>From Address</label>
                      <input
                        type="email"
                        value={emailForm.from_address}
                        onChange={e => setEmailForm(prev => ({ ...prev, from_address: e.target.value }))}
                        placeholder="noreply@example.com"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>From Name</label>
                      <input
                        type="text"
                        value={emailForm.from_name}
                        onChange={e => setEmailForm(prev => ({ ...prev, from_name: e.target.value }))}
                        placeholder="SHATTERED"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group form-checkbox">
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={emailForm.use_tls}
                          onChange={e => setEmailForm(prev => ({ ...prev, use_tls: e.target.checked }))}
                        />
                        <span className="toggle-slider" />
                      </label>
                      <span>Use TLS encryption</span>
                    </div>
                  </div>
                  <div className="form-actions">
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setShowEmailForm(false);
                        setEmailForm(DEFAULT_EMAIL_FORM);
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={saveEmailChannel}
                      disabled={savingChannel}
                    >
                      {savingChannel ? (
                        <>
                          <Icon name="Loader2" size={16} className="spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Icon name="Save" size={16} />
                          Save Email Channel
                        </>
                      )}
                    </button>
                  </div>
                </section>
              )}

              {/* Webhook Channel Form */}
              {showWebhookForm && (
                <section className="notifications-section channel-form">
                  <h3 className="section-title">
                    <Icon name="Webhook" size={18} />
                    Configure Webhook Channel
                  </h3>
                  <div className="form-grid">
                    <div className="form-group">
                      <label>Channel Name *</label>
                      <input
                        type="text"
                        value={webhookForm.name}
                        onChange={e => setWebhookForm(prev => ({ ...prev, name: e.target.value }))}
                        placeholder="e.g., slack-alerts"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group full-width">
                      <label>Webhook URL *</label>
                      <input
                        type="url"
                        value={webhookForm.url}
                        onChange={e => setWebhookForm(prev => ({ ...prev, url: e.target.value }))}
                        placeholder="https://hooks.slack.com/..."
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group">
                      <label>HTTP Method</label>
                      <select
                        value={webhookForm.method}
                        onChange={e => setWebhookForm(prev => ({ ...prev, method: e.target.value }))}
                        className="setting-select"
                      >
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="PATCH">PATCH</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label>Auth Token (optional)</label>
                      <input
                        type="password"
                        value={webhookForm.auth_token}
                        onChange={e => setWebhookForm(prev => ({ ...prev, auth_token: e.target.value }))}
                        placeholder="Bearer token or API key"
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group full-width">
                      <label>Custom Headers (JSON)</label>
                      <input
                        type="text"
                        value={webhookForm.headers}
                        onChange={e => setWebhookForm(prev => ({ ...prev, headers: e.target.value }))}
                        placeholder='{"X-Custom-Header": "value"}'
                        className="setting-input"
                      />
                    </div>
                    <div className="form-group form-checkbox">
                      <label className="toggle-switch">
                        <input
                          type="checkbox"
                          checked={webhookForm.verify_ssl}
                          onChange={e => setWebhookForm(prev => ({ ...prev, verify_ssl: e.target.checked }))}
                        />
                        <span className="toggle-slider" />
                      </label>
                      <span>Verify SSL certificate</span>
                    </div>
                  </div>
                  <div className="form-actions">
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setShowWebhookForm(false);
                        setWebhookForm(DEFAULT_WEBHOOK_FORM);
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn btn-primary"
                      onClick={saveWebhookChannel}
                      disabled={savingChannel}
                    >
                      {savingChannel ? (
                        <>
                          <Icon name="Loader2" size={16} className="spin" />
                          Saving...
                        </>
                      ) : (
                        <>
                          <Icon name="Save" size={16} />
                          Save Webhook Channel
                        </>
                      )}
                    </button>
                  </div>
                </section>
              )}
            </div>
          ) : activeCategory === 'shards' ? (
            // Shards Management UI
            shardsLoading ? (
              <div className="settings-loading">
                <Icon name="Loader2" size={32} className="spin" />
                <span>Loading shards...</span>
              </div>
            ) : shardsError ? (
              <div className="settings-error">
                <Icon name="AlertCircle" size={32} />
                <span>Failed to load shards</span>
                <button className="btn btn-secondary" onClick={() => refetchShards()}>
                  Retry
                </button>
              </div>
            ) : shardsData?.shards ? (
              <div className="shards-management">
                <div className="shards-header">
                  <p className="shards-description">
                    Manage which feature modules are active. Disabling a shard will unload it from memory
                    and hide it from navigation. Protected shards (Dashboard, Settings) cannot be disabled.
                  </p>
                  <div className="shards-stats">
                    <span className="stat">
                      <Icon name="Package" size={16} />
                      {shardsData.shards.filter(s => s.loaded).length} of {shardsData.shards.length} active
                    </span>
                  </div>
                </div>

                {Object.entries(groupShardsByCategory(shardsData.shards)).map(([category, shards]) => (
                  <div key={category} className="shard-category">
                    <h3 className="category-title">{category}</h3>
                    <div className="shards-list">
                      {shards.map(shard => {
                        const isProtected = PROTECTED_SHARDS.has(shard.name);
                        const isToggling = togglingShards.has(shard.name);

                        return (
                          <div
                            key={shard.name}
                            className={`shard-item ${shard.loaded ? 'loaded' : 'unloaded'} ${isProtected ? 'protected' : ''}`}
                          >
                            {/* Toggle on the left for clear association */}
                            <div className="shard-control">
                              {isToggling ? (
                                <div className="toggle-loading">
                                  <Icon name="Loader2" size={20} className="spin" />
                                </div>
                              ) : (
                                <label className={`toggle-switch shard-toggle ${isProtected ? 'disabled' : ''}`}>
                                  <input
                                    type="checkbox"
                                    checked={shard.enabled}
                                    onChange={e => toggleShard(shard.name, e.target.checked)}
                                    disabled={isProtected}
                                  />
                                  <span className="toggle-slider" />
                                </label>
                              )}
                            </div>
                            <div className="shard-icon">
                              <Icon name={shard.navigation?.icon || 'Package'} size={24} />
                            </div>
                            <div className="shard-info">
                              <div className="shard-header">
                                <span className="shard-name">
                                  {shard.navigation?.label || shard.name}
                                </span>
                                <span className="shard-version">v{shard.version}</span>
                                {isProtected && (
                                  <span className="protected-badge">
                                    <Icon name="Shield" size={12} />
                                    Protected
                                  </span>
                                )}
                              </div>
                              <p className="shard-description">{shard.description}</p>
                              {shard.capabilities && shard.capabilities.length > 0 && (
                                <div className="shard-capabilities">
                                  {(expandedCapabilities.has(shard.name)
                                    ? shard.capabilities
                                    : shard.capabilities.slice(0, 3)
                                  ).map(cap => (
                                    <span key={cap} className="capability-tag">{cap}</span>
                                  ))}
                                  {shard.capabilities.length > 3 && (
                                    <button
                                      className="capability-tag more"
                                      onClick={() => setExpandedCapabilities(prev => {
                                        const next = new Set(prev);
                                        if (next.has(shard.name)) {
                                          next.delete(shard.name);
                                        } else {
                                          next.add(shard.name);
                                        }
                                        return next;
                                      })}
                                    >
                                      {expandedCapabilities.has(shard.name)
                                        ? 'show less'
                                        : `+${shard.capabilities.length - 3} more`}
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="settings-empty">
                <Icon name="Puzzle" size={48} />
                <span>No shards available</span>
              </div>
            )
          ) : loading ? (
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

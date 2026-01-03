/**
 * LLMConfigTab - LLM configuration management with provider presets
 */

import { useState, useMemo, useEffect } from 'react';
import { Icon } from '../../../components/common/Icon';
import { useToast } from '../../../context/ToastContext';
import { useConfirm } from '../../../context/ConfirmContext';
import { useLLMConfig } from '../api';

// Provider preset configuration
interface LLMProvider {
  id: string;
  name: string;
  description: string;
  endpoint: string;
  defaultModel: string;
  models: string[];
  requiresApiKey: boolean;
  apiKeyEnvVar: string;
  icon: string;
  local: boolean;
}

const LLM_PROVIDERS: LLMProvider[] = [
  {
    id: 'lm-studio',
    name: 'LM Studio',
    description: 'Local LLM server with OpenAI-compatible API',
    endpoint: 'http://localhost:1234/v1',
    defaultModel: 'local-model',
    models: ['local-model'],
    requiresApiKey: false,
    apiKeyEnvVar: '',
    icon: 'Monitor',
    local: true,
  },
  {
    id: 'ollama',
    name: 'Ollama',
    description: 'Run LLMs locally with easy model management',
    endpoint: 'http://localhost:11434/v1',
    defaultModel: 'llama3.2',
    models: ['llama3.2', 'llama3.1', 'mistral', 'mixtral', 'phi3', 'gemma2', 'qwen2.5', 'codellama'],
    requiresApiKey: false,
    apiKeyEnvVar: '',
    icon: 'Box',
    local: true,
  },
  {
    id: 'openai',
    name: 'OpenAI',
    description: 'GPT-4o, GPT-4, and GPT-3.5 models',
    endpoint: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo'],
    requiresApiKey: true,
    apiKeyEnvVar: 'OPENAI_API_KEY',
    icon: 'Sparkles',
    local: false,
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    description: 'Access multiple LLM providers through one API',
    endpoint: 'https://openrouter.ai/api/v1',
    defaultModel: 'google/gemini-2.5-flash-lite',
    models: [
      'google/gemini-2.5-flash-lite',
      'google/gemini-2.5-flash',
      'meta-llama/llama-4-scout',
      'meta-llama/llama-4-maverick',
      'mistralai/mistral-small-3.1-24b-instruct',
      'anthropic/claude-3.5-sonnet',
      'openai/gpt-4o',
    ],
    requiresApiKey: true,
    apiKeyEnvVar: 'OPENROUTER_API_KEY',
    icon: 'Route',
    local: false,
  },
  {
    id: 'together',
    name: 'Together AI',
    description: 'Fast inference for open-source models',
    endpoint: 'https://api.together.xyz/v1',
    defaultModel: 'meta-llama/Llama-3.2-70B-Instruct-Turbo',
    models: ['meta-llama/Llama-3.2-70B-Instruct-Turbo', 'mistralai/Mixtral-8x7B-Instruct-v0.1', 'Qwen/Qwen2.5-72B-Instruct-Turbo'],
    requiresApiKey: true,
    apiKeyEnvVar: 'TOGETHER_API_KEY',
    icon: 'Users',
    local: false,
  },
  {
    id: 'groq',
    name: 'Groq',
    description: 'Ultra-fast LLM inference',
    endpoint: 'https://api.groq.com/openai/v1',
    defaultModel: 'llama-3.3-70b-versatile',
    models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    requiresApiKey: true,
    apiKeyEnvVar: 'GROQ_API_KEY',
    icon: 'Zap',
    local: false,
  },
  {
    id: 'custom',
    name: 'Custom Endpoint',
    description: 'Configure a custom OpenAI-compatible endpoint',
    endpoint: '',
    defaultModel: '',
    models: [],
    requiresApiKey: false,
    apiKeyEnvVar: 'LLM_API_KEY',
    icon: 'Settings',
    local: false,
  },
];

// API returns response as object with text property
interface TestResult {
  success: boolean;
  response?: { text: string; model?: string } | string;
  error?: string;
}

function getResponseText(response: TestResult['response']): string {
  if (!response) return '';
  if (typeof response === 'string') return response;
  return response.text || JSON.stringify(response);
}

export function LLMConfigTab() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const { config, loading, error, updateConfig, testConnection, resetConfig, setFallbackModels } = useLLMConfig();

  // Build providers with Docker-aware endpoints from backend config
  const providers = useMemo(() => {
    return LLM_PROVIDERS.map(p => {
      if (p.id === 'lm-studio' && config?.default_lm_studio_endpoint) {
        return { ...p, endpoint: config.default_lm_studio_endpoint };
      }
      if (p.id === 'ollama' && config?.default_ollama_endpoint) {
        return { ...p, endpoint: config.default_ollama_endpoint };
      }
      return p;
    });
  }, [config?.default_lm_studio_endpoint, config?.default_ollama_endpoint]);

  // Detect current provider from endpoint (handles both localhost and host.docker.internal)
  const detectProvider = (endpoint: string): LLMProvider | null => {
    if (!endpoint) return null;
    const normalizedEndpoint = endpoint.replace('host.docker.internal', 'localhost');
    return providers.find(p => {
      if (p.id === 'custom' || !p.endpoint) return false;
      const normalizedProviderEndpoint = p.endpoint.replace('host.docker.internal', 'localhost');
      try {
        return normalizedEndpoint.includes(new URL(normalizedProviderEndpoint).host);
      } catch {
        return false;
      }
    }) || null;
  };

  // Provider selection state
  const [selectedProviderId, setSelectedProviderId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [customEndpoint, setCustomEndpoint] = useState('');
  const [customModel, setCustomModel] = useState('');

  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [resetting, setResetting] = useState(false);

  // Fallback routing state
  const [fallbackModels, setFallbackModelsState] = useState<string[]>([]);
  const [newFallbackModel, setNewFallbackModel] = useState('');
  const [fallbackEnabled, setFallbackEnabled] = useState(false);
  const [savingFallback, setSavingFallback] = useState(false);

  const selectedProvider = providers.find(p => p.id === selectedProviderId);
  const currentProvider = config?.endpoint ? detectProvider(config.endpoint) : null;

  // Sync fallback state from config
  useEffect(() => {
    if (config) {
      setFallbackModelsState(config.fallback_models || []);
      setFallbackEnabled(config.fallback_routing_enabled || false);
    }
  }, [config]);

  // Fallback model handlers
  const handleAddFallbackModel = () => {
    if (!newFallbackModel.trim()) return;
    if (fallbackModels.includes(newFallbackModel.trim())) {
      toast.warning('Model already in fallback list');
      return;
    }
    setFallbackModelsState([...fallbackModels, newFallbackModel.trim()]);
    setNewFallbackModel('');
  };

  const handleRemoveFallbackModel = (model: string) => {
    setFallbackModelsState(fallbackModels.filter(m => m !== model));
  };

  const handleMoveFallbackModel = (index: number, direction: 'up' | 'down') => {
    const newModels = [...fallbackModels];
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= newModels.length) return;
    [newModels[index], newModels[newIndex]] = [newModels[newIndex], newModels[index]];
    setFallbackModelsState(newModels);
  };

  const handleSaveFallback = async () => {
    setSavingFallback(true);
    try {
      const result = await setFallbackModels(fallbackModels, fallbackEnabled);
      if (result.success) {
        toast.success('Fallback routing configuration saved');
      } else {
        toast.error(result.error || 'Failed to save fallback config');
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setSavingFallback(false);
    }
  };

  const handleProviderSelect = (providerId: string) => {
    const provider = providers.find(p => p.id === providerId);
    setSelectedProviderId(providerId);
    if (provider) {
      setSelectedModel(provider.defaultModel);
      if (providerId === 'custom') {
        setCustomEndpoint('');
        setCustomModel('');
      }
    }
  };

  const handleApplyProvider = async () => {
    if (!selectedProvider) return;

    let endpoint: string;
    let model: string;

    if (selectedProvider.id === 'custom') {
      if (!customEndpoint) {
        toast.warning('Please enter a custom endpoint URL');
        return;
      }
      endpoint = customEndpoint;
      model = customModel || 'local-model';
    } else {
      endpoint = selectedProvider.endpoint;
      model = selectedModel || selectedProvider.defaultModel;
    }

    setUpdating(true);
    try {
      await updateConfig(endpoint, model);
      toast.success(`Switched to ${selectedProvider.name}`);
      setSelectedProviderId('');
      setSelectedModel('');
      setCustomEndpoint('');
      setCustomModel('');
      setTestResult(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setUpdating(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await testConnection();
      setTestResult(result);
      if (result.success) {
        toast.success('LLM connection successful');
      } else {
        toast.error(result.error || 'Connection test failed');
      }
    } catch (e) {
      const err = (e as Error).message;
      setTestResult({ success: false, error: err });
      toast.error(err);
    } finally {
      setTesting(false);
    }
  };

  const handleReset = async () => {
    const defaultEndpoint = config?.default_lm_studio_endpoint || 'localhost:1234/v1';
    const confirmed = await confirm({
      title: 'Reset LLM Configuration',
      message: `This will reset to the default LM Studio configuration (${defaultEndpoint}). Continue?`,
      confirmLabel: 'Reset to Defaults',
      cancelLabel: 'Cancel',
      variant: 'default',
    });

    if (!confirmed) return;

    setResetting(true);
    try {
      await resetConfig();
      toast.success('LLM configuration reset to defaults');
      setSelectedProviderId('');
      setTestResult(null);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setResetting(false);
    }
  };

  if (loading) {
    return (
      <div className="tab-loading">
        <Icon name="Loader2" size={32} className="spin" />
        <span>Loading LLM configuration...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tab-error">
        <Icon name="AlertCircle" size={32} />
        <span>Failed to load LLM configuration</span>
        <p className="error-detail">{error}</p>
      </div>
    );
  }

  return (
    <div className="llm-config-tab">
      {/* Docker Mode Indicator */}
      {config?.is_docker && (
        <div className="docker-mode-banner">
          <Icon name="Box" size={16} />
          <span>Running in Docker - local endpoints use <code>host.docker.internal</code></span>
        </div>
      )}

      {/* Current Configuration */}
      <section className="config-section">
        <h3>
          <Icon name="Settings2" size={18} />
          Current Configuration
        </h3>
        <div className="config-card">
          <div className="config-header">
            <span className={`status-badge ${config?.available ? 'success' : 'error'}`}>
              {config?.available ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="config-details">
            <div className="config-row">
              <span className="config-label">Provider:</span>
              <span className="config-value-inline">
                {currentProvider ? (
                  <>
                    <Icon name={currentProvider.icon} size={16} />
                    {currentProvider.name}
                  </>
                ) : (
                  'Custom'
                )}
              </span>
            </div>
            <div className="config-row">
              <span className="config-label">Endpoint:</span>
              <code className="config-value">{config?.endpoint || 'Not configured'}</code>
            </div>
            <div className="config-row">
              <span className="config-label">Model:</span>
              <code className="config-value">{config?.model || 'Not configured'}</code>
            </div>
            <div className="config-row">
              <span className="config-label">API Key:</span>
              {config?.api_key_configured ? (
                <span className="status-badge success">
                  Configured ({config.api_key_source})
                </span>
              ) : (
                <span className="status-badge warning">Not Set</span>
              )}
            </div>
          </div>
          <div className="config-actions">
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleTest}
              disabled={testing}
            >
              {testing ? (
                <>
                  <Icon name="Loader2" size={14} className="spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Icon name="Zap" size={14} />
                  Test Connection
                </>
              )}
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleReset}
              disabled={resetting}
            >
              {resetting ? (
                <>
                  <Icon name="Loader2" size={14} className="spin" />
                  Resetting...
                </>
              ) : (
                <>
                  <Icon name="RotateCcw" size={14} />
                  Reset to Defaults
                </>
              )}
            </button>
          </div>
        </div>
      </section>

      {/* Test Result */}
      {testResult && (
        <section className="result-section">
          <div className={`result-card ${testResult.success ? 'success' : 'error'}`}>
            <div className="result-header">
              <Icon name={testResult.success ? 'CheckCircle' : 'XCircle'} size={20} />
              <span>Test Result</span>
              <span className={`status-badge ${testResult.success ? 'success' : 'error'}`}>
                {testResult.success ? 'Success' : 'Failed'}
              </span>
            </div>
            <div className="result-content">
              {testResult.success ? (
                <p>LLM responded: <em>"{getResponseText(testResult.response)}"</em></p>
              ) : (
                <p className="error-text">{testResult.error}</p>
              )}
            </div>
          </div>
        </section>
      )}

      {/* Provider Selection */}
      <section className="provider-section">
        <h3>
          <Icon name="Layers" size={18} />
          Switch Provider
        </h3>

        <div className="provider-grid">
          {providers.map((provider) => (
            <button
              key={provider.id}
              className={`provider-card ${selectedProviderId === provider.id ? 'selected' : ''} ${currentProvider?.id === provider.id ? 'current' : ''}`}
              onClick={() => handleProviderSelect(provider.id)}
            >
              <div className="provider-icon">
                <Icon name={provider.icon} size={24} />
              </div>
              <div className="provider-info">
                <span className="provider-name">{provider.name}</span>
                <span className="provider-desc">{provider.description}</span>
              </div>
              <div className="provider-badges">
                {provider.local && (
                  <span className="provider-badge local">Local</span>
                )}
                {provider.requiresApiKey && (
                  <span className="provider-badge api-key">API Key</span>
                )}
                {currentProvider?.id === provider.id && (
                  <span className="provider-badge active">Active</span>
                )}
              </div>
            </button>
          ))}
        </div>

        {/* Provider Configuration Panel */}
        {selectedProvider && (
          <div className="provider-config">
            <h4>Configure {selectedProvider.name}</h4>

            {/* API Key Warning for cloud providers */}
            {selectedProvider.requiresApiKey && !config?.api_key_configured && (
              <div className="api-key-warning">
                <Icon name="AlertTriangle" size={20} />
                <div className="warning-content">
                  <strong>API Key Required</strong>
                  <p>
                    {selectedProvider.name} requires an API key. Set it as an environment variable before switching:
                  </p>
                  <div className="env-var-box">
                    <code>{selectedProvider.apiKeyEnvVar}=your-api-key-here</code>
                  </div>
                  <p className="hint">
                    Add this to your <code>.env</code> file or set it in your terminal, then restart the server.
                  </p>
                </div>
              </div>
            )}

            {/* API Key Confirmed for cloud providers */}
            {selectedProvider.requiresApiKey && config?.api_key_configured && (
              <div className="api-key-confirmed">
                <Icon name="CheckCircle" size={20} />
                <span>API key detected from <code>{config.api_key_source}</code></span>
              </div>
            )}

            {/* Model Selection */}
            {selectedProvider.id !== 'custom' && selectedProvider.models.length > 0 && (
              <div className="form-group">
                <label className="form-label">Model</label>
                {selectedProvider.id === 'openrouter' ? (
                  <>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="e.g., google/gemini-2.5-flash-lite"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      list="openrouter-models"
                    />
                    <datalist id="openrouter-models">
                      {selectedProvider.models.map((model) => (
                        <option key={model} value={model} />
                      ))}
                    </datalist>
                    <span className="form-hint">
                      Type any OpenRouter model ID or select from suggestions
                    </span>
                  </>
                ) : (
                  <select
                    className="form-select"
                    value={selectedModel}
                    onChange={(e) => setSelectedModel(e.target.value)}
                  >
                    {selectedProvider.models.map((model) => (
                      <option key={model} value={model}>{model}</option>
                    ))}
                  </select>
                )}
              </div>
            )}

            {/* Custom Endpoint Configuration */}
            {selectedProvider.id === 'custom' && (
              <>
                <div className="form-group">
                  <label className="form-label">Endpoint URL</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder={config?.is_docker ? "http://host.docker.internal:8080/v1" : "http://localhost:8080/v1"}
                    value={customEndpoint}
                    onChange={(e) => setCustomEndpoint(e.target.value)}
                  />
                  <span className="form-hint">
                    OpenAI-compatible API endpoint
                    {config?.is_docker && " (use host.docker.internal for host services)"}
                  </span>
                </div>
                <div className="form-group">
                  <label className="form-label">Model Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="local-model"
                    value={customModel}
                    onChange={(e) => setCustomModel(e.target.value)}
                  />
                  <span className="form-hint">Model identifier for the server</span>
                </div>
              </>
            )}

            {/* Endpoint Preview */}
            {selectedProvider.id !== 'custom' && (
              <div className="endpoint-preview">
                <span className="preview-label">Endpoint:</span>
                <code>{selectedProvider.endpoint}</code>
              </div>
            )}

            {/* Apply Button */}
            <div className="btn-group">
              <button
                className="btn btn-primary"
                onClick={handleApplyProvider}
                disabled={updating || (selectedProvider.id === 'custom' && !customEndpoint)}
              >
                {updating ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Applying...
                  </>
                ) : (
                  <>
                    <Icon name="Check" size={16} />
                    Apply Configuration
                  </>
                )}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => setSelectedProviderId('')}
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </section>

      {/* OpenRouter Fallback Routing */}
      {config?.is_openrouter && (
        <section className="fallback-section">
          <h3>
            <Icon name="GitBranch" size={18} />
            Fallback Routing
          </h3>
          <p className="section-description">
            Configure fallback models for automatic failover when your primary model
            is unavailable (quota exceeded, rate limited, etc).
          </p>

          <div className="fallback-config">
            <div className="toggle-row">
              <label className="toggle-label">
                <input
                  type="checkbox"
                  checked={fallbackEnabled}
                  onChange={(e) => setFallbackEnabled(e.target.checked)}
                />
                Enable fallback routing
              </label>
            </div>

            <div className="fallback-models">
              <label className="form-label">Fallback Models (in priority order)</label>

              {fallbackModels.length === 0 ? (
                <div className="empty-fallback">
                  <Icon name="Info" size={16} />
                  <span>No fallback models configured</span>
                </div>
              ) : (
                <ul className="fallback-list">
                  {fallbackModels.map((model, index) => (
                    <li key={model} className="fallback-item">
                      <span className="fallback-priority">{index + 1}</span>
                      <code className="fallback-model-name">{model}</code>
                      <div className="fallback-actions">
                        <button
                          className="btn btn-icon"
                          onClick={() => handleMoveFallbackModel(index, 'up')}
                          disabled={index === 0}
                          title="Move up"
                        >
                          <Icon name="ChevronUp" size={14} />
                        </button>
                        <button
                          className="btn btn-icon"
                          onClick={() => handleMoveFallbackModel(index, 'down')}
                          disabled={index === fallbackModels.length - 1}
                          title="Move down"
                        >
                          <Icon name="ChevronDown" size={14} />
                        </button>
                        <button
                          className="btn btn-icon btn-danger"
                          onClick={() => handleRemoveFallbackModel(model)}
                          title="Remove"
                        >
                          <Icon name="X" size={14} />
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              <div className="add-fallback">
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g., google/gemini-2.0-flash-exp"
                  value={newFallbackModel}
                  onChange={(e) => setNewFallbackModel(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleAddFallbackModel()}
                />
                <button
                  className="btn btn-secondary"
                  onClick={handleAddFallbackModel}
                  disabled={!newFallbackModel.trim()}
                >
                  <Icon name="Plus" size={14} />
                  Add
                </button>
              </div>
              <span className="form-hint">
                Use OpenRouter model IDs like <code>google/gemini-2.0-flash-exp</code>
              </span>
            </div>

            <div className="btn-group">
              <button
                className="btn btn-primary"
                onClick={handleSaveFallback}
                disabled={savingFallback}
              >
                {savingFallback ? (
                  <>
                    <Icon name="Loader2" size={16} className="spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Icon name="Save" size={16} />
                    Save Fallback Config
                  </>
                )}
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}

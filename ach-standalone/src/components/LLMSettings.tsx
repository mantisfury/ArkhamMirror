import { useState } from 'react';
import { useACHStore } from '../store/useACHStore';
import { LLM_PROVIDERS, LLMProvider } from '../types';
import { Button, Dialog, Input, Select } from './ui';
import {
  Wifi, WifiOff, Loader2, CheckCircle, XCircle,
  Eye, EyeOff, AlertTriangle, Server, Cloud, Key
} from 'lucide-react';

interface LLMSettingsProps {
  open: boolean;
  onClose: () => void;
}

export function LLMSettings({ open, onClose }: LLMSettingsProps) {
  const llmConfig = useACHStore((state) => state.llmConfig);
  const setLLMConfig = useACHStore((state) => state.setLLMConfig);
  const setLLMProvider = useACHStore((state) => state.setLLMProvider);
  const testLLMConnection = useACHStore((state) => state.testLLMConnection);

  const [showApiKey, setShowApiKey] = useState(false);
  const [isTesting, setIsTesting] = useState(false);

  const providerConfig = LLM_PROVIDERS[llmConfig.provider];
  const isCloudProvider = providerConfig.requiresApiKey;
  const isLocalProvider = llmConfig.provider === 'lmstudio' || llmConfig.provider === 'ollama';

  const handleProviderChange = (provider: LLMProvider) => {
    setLLMProvider(provider);
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    await testLLMConnection();
    setIsTesting(false);
  };

  const providerOptions = Object.entries(LLM_PROVIDERS).map(([key, config]) => ({
    value: key,
    label: config.name,
  }));

  const getStatusIcon = () => {
    if (isTesting) {
      return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
    }
    switch (llmConfig.connectionStatus) {
      case 'connected':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'error':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <WifiOff className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusText = () => {
    if (isTesting) return 'Testing...';
    switch (llmConfig.connectionStatus) {
      case 'connected':
        return 'Connected';
      case 'error':
        return 'Connection failed';
      default:
        return 'Not tested';
    }
  };

  return (
    <Dialog open={open} onClose={onClose} title="LLM Settings" size="lg">
      <div className="space-y-6">
        {/* Enable/Disable Toggle */}
        <div className="flex items-center justify-between p-4 bg-gray-800 rounded-lg border border-gray-700">
          <div className="flex items-center gap-3">
            {llmConfig.enabled ? (
              <Wifi className="w-5 h-5 text-green-400" />
            ) : (
              <WifiOff className="w-5 h-5 text-gray-500" />
            )}
            <div>
              <p className="text-white font-medium">LLM Integration</p>
              <p className="text-sm text-gray-400">
                Enable AI-assisted analysis features
              </p>
            </div>
          </div>
          <button
            onClick={() => setLLMConfig({ enabled: !llmConfig.enabled })}
            className={`relative w-12 h-6 rounded-full transition-colors ${
              llmConfig.enabled ? 'bg-blue-600' : 'bg-gray-600'
            }`}
          >
            <span
              className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                llmConfig.enabled ? 'translate-x-6' : 'translate-x-0.5'
              }`}
            />
          </button>
        </div>

        {/* Provider Selection */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-gray-400" />
            <h3 className="text-white font-medium">Provider</h3>
          </div>

          <Select
            value={llmConfig.provider}
            onChange={(e) => handleProviderChange(e.target.value as LLMProvider)}
            options={providerOptions}
          />

          {/* Provider Info */}
          <div className={`p-3 rounded-lg border ${
            isLocalProvider
              ? 'bg-green-900/20 border-green-800'
              : 'bg-yellow-900/20 border-yellow-800'
          }`}>
            <div className="flex items-start gap-2">
              {isLocalProvider ? (
                <Server className="w-4 h-4 text-green-400 mt-0.5" />
              ) : (
                <Cloud className="w-4 h-4 text-yellow-400 mt-0.5" />
              )}
              <div>
                <p className={`text-sm ${isLocalProvider ? 'text-green-300' : 'text-yellow-300'}`}>
                  {isLocalProvider
                    ? 'Local Provider - Your data stays on your machine'
                    : 'Cloud Provider - Data will be sent to external servers'
                  }
                </p>
                {isLocalProvider && (
                  <p className="text-xs text-green-400/70 mt-1">
                    Tip: Enable CORS in your local server (LM Studio: Settings &gt; Server &gt; Enable CORS)
                  </p>
                )}
                {isCloudProvider && (
                  <p className="text-xs text-yellow-400/70 mt-1">
                    API keys are stored locally in your browser only.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Endpoint Configuration */}
        <div className="space-y-3">
          <Input
            label="Endpoint URL"
            value={llmConfig.endpoint}
            onChange={(e) => setLLMConfig({ endpoint: e.target.value })}
            placeholder={providerConfig.defaultEndpoint}
          />
          {llmConfig.provider === 'custom' && (
            <p className="text-xs text-gray-500">
              Enter your custom OpenAI-compatible endpoint
            </p>
          )}
        </div>

        {/* API Key (for cloud providers) */}
        {isCloudProvider && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4 text-gray-400" />
              <h3 className="text-white font-medium">API Key</h3>
            </div>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={llmConfig.apiKey || ''}
                onChange={(e) => setLLMConfig({ apiKey: e.target.value })}
                placeholder="Enter your API key"
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 pr-10 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              >
                {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {!llmConfig.apiKey && (
              <div className="flex items-center gap-2 text-yellow-400 text-sm">
                <AlertTriangle className="w-4 h-4" />
                <span>API key required for {providerConfig.name}</span>
              </div>
            )}
          </div>
        )}

        {/* Model Selection */}
        <div className="space-y-3">
          <Input
            label="Model"
            value={llmConfig.model}
            onChange={(e) => setLLMConfig({ model: e.target.value })}
            placeholder={providerConfig.defaultModel}
          />
          <p className="text-xs text-gray-500">
            {llmConfig.provider === 'lmstudio' && 'Use the model currently loaded in LM Studio'}
            {llmConfig.provider === 'ollama' && 'e.g., llama3.2, mistral, codellama'}
            {llmConfig.provider === 'openai' && 'e.g., gpt-4o, gpt-4o-mini, gpt-3.5-turbo'}
            {llmConfig.provider === 'groq' && 'e.g., llama-3.3-70b-versatile, mixtral-8x7b-32768'}
            {llmConfig.provider === 'anthropic' && 'e.g., claude-3-5-sonnet-20241022, claude-3-haiku-20240307'}
            {llmConfig.provider === 'custom' && 'Model identifier for your custom endpoint'}
          </p>
        </div>

        {/* Connection Status */}
        <div className="p-4 bg-gray-800 rounded-lg border border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <div>
                <p className="text-white font-medium">{getStatusText()}</p>
                {llmConfig.connectionStatus === 'error' && llmConfig.lastError && (
                  <p className="text-sm text-red-400 mt-1">{llmConfig.lastError}</p>
                )}
              </div>
            </div>
            <Button
              onClick={handleTestConnection}
              variant="secondary"
              size="sm"
              disabled={isTesting || (isCloudProvider && !llmConfig.apiKey)}
            >
              {isTesting ? 'Testing...' : 'Test Connection'}
            </Button>
          </div>
        </div>

        {/* Privacy Notice */}
        <div className="p-3 bg-gray-900 rounded-lg border border-gray-700">
          <p className="text-xs text-gray-400">
            <strong className="text-gray-300">Privacy Note:</strong> When LLM features are enabled,
            your analysis data (hypotheses, evidence, ratings) may be sent to the selected provider
            for AI processing. For maximum privacy, use a local provider like LM Studio or Ollama.
            API keys are stored only in your browser's localStorage and are never sent to our servers.
          </p>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

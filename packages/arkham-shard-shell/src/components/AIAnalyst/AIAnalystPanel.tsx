/**
 * AI Junior Analyst Panel - Collapsible right-side panel for AI analysis
 *
 * Features:
 * - Streaming responses with markdown rendering
 * - Conversation history with follow-up questions
 * - Context-aware analysis
 * - Resizable panel width
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { Icon } from '../common/Icon';
import type { AIAnalystPanelProps, AIAnalystState, Message, StreamEvent } from './types';
import './AIAnalystPanel.css';

const SHARD_TITLES: Record<string, string> = {
  graph: 'Network Analysis',
  timeline: 'Timeline Analysis',
  ach: 'Matrix Analysis',
  anomalies: 'Anomaly Analysis',
  contradictions: 'Conflict Analysis',
  patterns: 'Pattern Analysis',
  entities: 'Entity Analysis',
  claims: 'Claim Assessment',
  credibility: 'Credibility Analysis',
  provenance: 'Source Tracing',
  documents: 'Document Summary',
};

export function AIAnalystPanel({
  shard,
  targetId,
  context,
  isOpen,
  onClose,
  title,
}: AIAnalystPanelProps) {
  const [state, setState] = useState<AIAnalystState>({
    sessionId: null,
    messages: [],
    isStreaming: false,
    context,
    error: null,
  });
  const [followUpInput, setFollowUpInput] = useState('');
  const [panelWidth, setPanelWidth] = useState(400);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const isResizing = useRef(false);

  // Auto-scroll to bottom of messages
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [state.messages, scrollToBottom]);

  // Reset conversation when context changes (new item selected)
  useEffect(() => {
    if (JSON.stringify(context) !== JSON.stringify(state.context)) {
      setState({
        sessionId: null,
        messages: [],
        isStreaming: false,
        context,
        error: null,
      });
    }
  }, [context, state.context]);

  // Run initial analysis when panel opens
  useEffect(() => {
    if (isOpen && state.messages.length === 0 && !state.isStreaming) {
      runAnalysis(null);
    }
  }, [isOpen]);

  // Run analysis (initial or follow-up)
  const runAnalysis = async (followUpMessage: string | null) => {
    setState(s => ({ ...s, isStreaming: true, error: null }));

    // Add user message if follow-up
    if (followUpMessage) {
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: followUpMessage,
        timestamp: new Date(),
      };
      setState(s => ({ ...s, messages: [...s.messages, userMessage] }));
    }

    try {
      const response = await fetch(`/api/${shard}/ai/junior-analyst`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_id: targetId,
          context,
          session_id: state.sessionId,
          message: followUpMessage,
          conversation_history: state.messages.map(m => ({
            role: m.role,
            content: m.content,
          })),
          depth: 'quick',
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Analysis failed (${response.status})`);
      }

      // Stream the response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      const messageId = crypto.randomUUID();

      // Add empty assistant message that we'll stream into
      setState(s => ({
        ...s,
        messages: [
          ...s.messages,
          {
            id: messageId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
          },
        ],
      }));

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      // Read the stream
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          try {
            const event: StreamEvent = JSON.parse(line.slice(6));

            switch (event.type) {
              case 'session':
                setState(s => ({ ...s, sessionId: event.session_id || null }));
                break;

              case 'text':
                assistantContent += event.content || '';
                setState(s => ({
                  ...s,
                  messages: s.messages.map(m =>
                    m.id === messageId ? { ...m, content: assistantContent } : m
                  ),
                }));
                break;

              case 'done':
                setState(s => ({ ...s, isStreaming: false }));
                break;

              case 'error':
                throw new Error(event.error || 'Stream error');
            }
          } catch (parseError) {
            // Ignore parse errors for malformed lines
            console.warn('Failed to parse stream event:', line);
          }
        }
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Analysis failed';
      setState(s => ({
        ...s,
        isStreaming: false,
        error: errorMessage,
      }));
    }
  };

  // Handle follow-up submission
  const handleFollowUp = () => {
    const trimmed = followUpInput.trim();
    if (trimmed && !state.isStreaming) {
      runAnalysis(trimmed);
      setFollowUpInput('');
    }
  };

  // Handle key press in input
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleFollowUp();
    }
  };

  // Clear conversation
  const clearConversation = () => {
    setState({
      sessionId: null,
      messages: [],
      isStreaming: false,
      context,
      error: null,
    });
  };

  // Submit feedback
  const submitFeedback = async (messageId: string, rating: 'up' | 'down') => {
    try {
      await fetch(`/api/${shard}/ai/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: state.sessionId || 'unknown',
          message_id: messageId,
          rating,
        }),
      });

      // Update message with feedback
      setState(s => ({
        ...s,
        messages: s.messages.map(m =>
          m.id === messageId ? { ...m, feedback: rating } : m
        ),
      }));
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

  // Resize handling
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', stopResize);
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing.current || !panelRef.current) return;
    const newWidth = window.innerWidth - e.clientX;
    setPanelWidth(Math.max(300, Math.min(600, newWidth)));
  }, []);

  const stopResize = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResize);
  }, [handleMouseMove]);

  // Panel title
  const panelTitle = title || SHARD_TITLES[shard] || 'AI Analysis';

  if (!isOpen) return null;

  return (
    <div
      className="ai-analyst-panel"
      ref={panelRef}
      style={{ width: panelWidth }}
    >
      {/* Resize handle */}
      <div className="ai-analyst-resize-handle" onMouseDown={startResize} />

      {/* Header */}
      <div className="ai-analyst-header">
        <div className="ai-analyst-title">
          <Icon name="Sparkles" size={18} />
          <span>{panelTitle}</span>
        </div>
        <div className="ai-analyst-header-actions">
          <button
            className="ai-analyst-btn-icon"
            onClick={clearConversation}
            title="Clear conversation"
            disabled={state.isStreaming}
          >
            <Icon name="RotateCcw" size={16} />
          </button>
          <button
            className="ai-analyst-btn-icon"
            onClick={onClose}
            title="Close panel"
          >
            <Icon name="X" size={16} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="ai-analyst-messages">
        {state.messages.length === 0 && !state.isStreaming && (
          <div className="ai-analyst-empty">
            <Icon name="Sparkles" size={32} />
            <p>Starting analysis...</p>
          </div>
        )}

        {state.messages.map(msg => (
          <div key={msg.id} className={`ai-analyst-message ${msg.role}`}>
            <div className="ai-analyst-message-header">
              <Icon
                name={msg.role === 'user' ? 'User' : 'Bot'}
                size={14}
              />
              <span>{msg.role === 'user' ? 'You' : 'AI Analyst'}</span>
            </div>
            <div className="ai-analyst-message-content">
              <ReactMarkdown>{msg.content || '...'}</ReactMarkdown>
            </div>

            {/* Feedback buttons for assistant messages */}
            {msg.role === 'assistant' && msg.content && !state.isStreaming && (
              <div className="ai-analyst-feedback">
                <span className="feedback-label">Helpful?</span>
                <button
                  className={`feedback-btn ${msg.feedback === 'up' ? 'active' : ''}`}
                  onClick={() => submitFeedback(msg.id, 'up')}
                  disabled={msg.feedback !== undefined}
                  title="Helpful"
                >
                  <Icon name="ThumbsUp" size={14} />
                </button>
                <button
                  className={`feedback-btn ${msg.feedback === 'down' ? 'active' : ''}`}
                  onClick={() => submitFeedback(msg.id, 'down')}
                  disabled={msg.feedback !== undefined}
                  title="Not helpful"
                >
                  <Icon name="ThumbsDown" size={14} />
                </button>
                {msg.feedback && (
                  <span className="feedback-thanks">Thanks!</span>
                )}
              </div>
            )}
          </div>
        ))}

        {state.isStreaming && (
          <div className="ai-analyst-streaming">
            <Icon name="Loader2" size={16} className="spin" />
            <span>Analyzing...</span>
          </div>
        )}

        {state.error && (
          <div className="ai-analyst-error">
            <Icon name="AlertCircle" size={16} />
            <span>{state.error}</span>
            <button
              className="ai-analyst-retry"
              onClick={() => runAnalysis(null)}
            >
              Retry
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Follow-up input */}
      <div className="ai-analyst-input">
        <input
          type="text"
          placeholder="Ask a follow-up question..."
          value={followUpInput}
          onChange={e => setFollowUpInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={state.isStreaming}
        />
        <button
          className="ai-analyst-send"
          onClick={handleFollowUp}
          disabled={!followUpInput.trim() || state.isStreaming}
          title="Send"
        >
          <Icon name="Send" size={16} />
        </button>
      </div>

      {/* Footer */}
      <div className="ai-analyst-footer">
        <span className="ai-analyst-hint">
          Try: "Tell me more about..." or "Why is that important?"
        </span>
      </div>
    </div>
  );
}

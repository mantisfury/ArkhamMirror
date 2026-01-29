/**
 * RAGChatPanel - Conversational Q&A interface grounded in document corpus
 *
 * Features:
 * - Streaming responses with citations
 * - Conversation history support
 * - Clickable citation links to source documents
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import { Icon } from '../../components/common/Icon';
import { apiFetch, apiGet, apiPost } from '../../utils/api';
import './RAGChatPanel.css';

interface Citation {
  chunk_id: string;
  doc_id: string;
  title: string;
  page_number: number | null;
  excerpt: string;
  score: number;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
  feedback?: 'up' | 'down' | null;
}

interface Project {
  id: string;
  name: string;
}

interface RAGChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  initialQuestion?: string;
  projectId?: string;
}

export function RAGChatPanel({ isOpen, onClose, initialQuestion, projectId }: RAGChatPanelProps) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [lastInitialQuestion, setLastInitialQuestion] = useState<string | undefined>();
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [panelWidth, setPanelWidth] = useState(450);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string | undefined>(projectId);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const isResizing = useRef(false);

  // Fetch projects on mount
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const data = await apiGet<any>('/api/projects/');
        const list = (data?.projects ?? data?.items) as unknown;
        setProjects(Array.isArray(list) ? list : []);
      } catch (err) {
        console.warn('Failed to fetch projects:', err);
      }
    };
    fetchProjects();
  }, []);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Handle initial question when panel opens with a new question
  useEffect(() => {
    if (isOpen && initialQuestion && initialQuestion !== lastInitialQuestion) {
      setLastInitialQuestion(initialQuestion);
      setInput(initialQuestion);
    }
  }, [isOpen, initialQuestion, lastInitialQuestion]);

  // Send message
  const sendMessage = async () => {
    const question = input.trim();
    if (!question || isStreaming) return;

    setInput('');
    setError(null);
    setIsStreaming(true);

    // Add user message
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);

    // Create empty assistant message to stream into
    const assistantId = crypto.randomUUID();
    setMessages(prev => [
      ...prev,
      {
        id: assistantId,
        role: 'assistant',
        content: '',
        citations: [],
        timestamp: new Date(),
      },
    ]);

    try {
      const response = await apiFetch('/api/search/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          conversation_id: conversationId,
          k_chunks: 10,
          similarity_threshold: 0.5,
          project_id: selectedProject || null,
          conversation_history: messages.map(m => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Chat failed (${response.status})`);
      }

      // Stream the response
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';
      let citations: Citation[] = [];

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          try {
            const event = JSON.parse(line.slice(6));

            switch (event.type) {
              case 'session':
                setConversationId(event.conversation_id);
                break;

              case 'citations':
                citations = event.citations || [];
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId ? { ...m, citations } : m
                  )
                );
                break;

              case 'text':
                assistantContent += event.content || '';
                setMessages(prev =>
                  prev.map(m =>
                    m.id === assistantId
                      ? { ...m, content: assistantContent }
                      : m
                  )
                );
                break;

              case 'error':
                throw new Error(event.error || 'Stream error');

              case 'done':
                break;
            }
          } catch (parseError) {
            console.warn('Failed to parse stream event:', line);
          }
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Chat failed';
      setError(errorMessage);
      // Remove the empty assistant message on error
      setMessages(prev => prev.filter(m => m.id !== assistantId));
    } finally {
      setIsStreaming(false);
    }
  };

  // Handle enter key
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Navigate to document
  const handleCitationClick = (citation: Citation) => {
    navigate(`/documents?id=${citation.doc_id}`);
    onClose();
  };

  // Clear conversation
  const clearConversation = () => {
    setMessages([]);
    setConversationId(null);
    setError(null);
  };

  // Submit feedback
  const submitFeedback = async (messageId: string, rating: 'up' | 'down') => {
    try {
      await apiPost('/api/search/ai/feedback', {
        session_id: conversationId || 'unknown',
        message_id: messageId,
        rating,
      });

      // Update message with feedback
      setMessages(prev =>
        prev.map(m =>
          m.id === messageId ? { ...m, feedback: rating } : m
        )
      );
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
    setPanelWidth(Math.max(350, Math.min(700, newWidth)));
  }, []);

  const stopResize = useCallback(() => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', stopResize);
  }, [handleMouseMove]);

  if (!isOpen) return null;

  return (
    <div
      className="rag-chat-panel"
      ref={panelRef}
      style={{ width: panelWidth }}
    >
      {/* Resize handle */}
      <div className="rag-chat-resize-handle" onMouseDown={startResize} />

      {/* Header */}
      <div className="rag-chat-header">
        <div className="rag-chat-title">
          <Icon name="MessageSquare" size={18} />
          <span>Ask AI</span>
        </div>
        <div className="rag-chat-header-actions">
          <button
            className="rag-chat-btn-icon"
            onClick={clearConversation}
            title="Clear conversation"
            disabled={isStreaming}
          >
            <Icon name="RotateCcw" size={16} />
          </button>
          <button
            className="rag-chat-btn-icon"
            onClick={onClose}
            title="Close panel"
          >
            <Icon name="X" size={16} />
          </button>
        </div>
      </div>

      {/* Project Selector */}
      {projects.length > 0 && (
        <div className="rag-chat-project-selector">
          <Icon name="Folder" size={14} />
          <select
            value={selectedProject || ''}
            onChange={(e) => setSelectedProject(e.target.value || undefined)}
            disabled={isStreaming}
          >
            <option value="">All Projects</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Messages */}
      <div className="rag-chat-messages">
        {messages.length === 0 && (
          <div className="rag-chat-empty">
            <Icon name="MessageSquare" size={32} />
            <h3>Ask about your documents</h3>
            <p>Ask questions and get answers grounded in your document corpus with source citations.</p>
            <div className="rag-chat-suggestions">
              <button onClick={() => setInput('What are the main topics in my documents?')}>
                What are the main topics?
              </button>
              <button onClick={() => setInput('Summarize the key findings')}>
                Summarize key findings
              </button>
              <button onClick={() => setInput('What people or organizations are mentioned?')}>
                Who is mentioned?
              </button>
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`rag-chat-message ${msg.role}`}>
            <div className="rag-chat-message-header">
              <Icon name={msg.role === 'user' ? 'User' : 'Bot'} size={14} />
              <span>{msg.role === 'user' ? 'You' : 'AI Assistant'}</span>
            </div>
            <div className="rag-chat-message-content">
              <ReactMarkdown>{msg.content || '...'}</ReactMarkdown>
            </div>

            {/* Citations */}
            {msg.citations && msg.citations.length > 0 && (
              <div className="rag-chat-citations">
                <div className="citations-header">
                  <Icon name="FileText" size={12} />
                  <span>Sources ({msg.citations.length})</span>
                </div>
                <div className="citations-list">
                  {msg.citations.map((citation, idx) => (
                    <button
                      key={`${citation.chunk_id}-${idx}`}
                      className="citation-item"
                      onClick={() => handleCitationClick(citation)}
                      title={citation.excerpt}
                    >
                      <span className="citation-number">{idx + 1}</span>
                      <span className="citation-title">{citation.title}</span>
                      {citation.page_number && (
                        <span className="citation-page">p.{citation.page_number}</span>
                      )}
                      <span className="citation-score">
                        {Math.round(citation.score * 100)}%
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Feedback buttons for assistant messages */}
            {msg.role === 'assistant' && msg.content && !isStreaming && (
              <div className="rag-chat-feedback">
                <span className="feedback-label">Was this helpful?</span>
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
                  <span className="feedback-thanks">Thanks for your feedback!</span>
                )}
              </div>
            )}
          </div>
        ))}

        {isStreaming && (
          <div className="rag-chat-streaming">
            <Icon name="Loader2" size={16} className="spin" />
            <span>Thinking...</span>
          </div>
        )}

        {error && (
          <div className="rag-chat-error">
            <Icon name="AlertCircle" size={16} />
            <span>{error}</span>
            <button className="rag-chat-retry" onClick={sendMessage}>
              Retry
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="rag-chat-input">
        <input
          type="text"
          placeholder="Ask a question about your documents..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isStreaming}
        />
        <button
          className="rag-chat-send"
          onClick={sendMessage}
          disabled={!input.trim() || isStreaming}
          title="Send"
        >
          <Icon name="Send" size={16} />
        </button>
      </div>

      {/* Footer */}
      <div className="rag-chat-footer">
        <span className="rag-chat-hint">
          Answers are grounded in your document corpus. Click citations to view sources.
        </span>
      </div>
    </div>
  );
}

/**
 * AI Junior Analyst - Type definitions
 */

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  feedback?: 'up' | 'down' | null;
}

export interface AIAnalystState {
  sessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  context: Record<string, unknown>;
  error: string | null;
}

export interface AIAnalystPanelProps {
  /** Shard name (e.g., "graph", "timeline", "ach") */
  shard: string;
  /** ID of the target item being analyzed */
  targetId: string;
  /** Serialized context data for analysis */
  context: Record<string, unknown>;
  /** Whether the panel is open */
  isOpen: boolean;
  /** Callback to close the panel */
  onClose: () => void;
  /** Optional title override */
  title?: string;
}

export interface AIAnalystButtonProps {
  /** Shard name (e.g., "graph", "timeline", "ach") */
  shard: string;
  /** ID of the target item being analyzed */
  targetId: string;
  /** Serialized context data for analysis */
  context: Record<string, unknown>;
  /** Optional button label */
  label?: string;
  /** Button variant */
  variant?: 'primary' | 'secondary' | 'ghost';
  /** Button size */
  size?: 'sm' | 'md' | 'lg';
  /** Whether button is disabled */
  disabled?: boolean;
}

export interface StreamEvent {
  type: 'session' | 'text' | 'done' | 'error';
  session_id?: string;
  content?: string;
  finish_reason?: string;
  error?: string;
}

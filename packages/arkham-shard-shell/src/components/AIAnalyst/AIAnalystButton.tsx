/**
 * AI Junior Analyst Button - Trigger button for AI analysis panel
 *
 * Use this component to add AI analysis capability to any shard.
 * It handles panel state internally.
 */

import { useState } from 'react';
import { Icon } from '../common/Icon';
import { AIAnalystPanel } from './AIAnalystPanel';
import type { AIAnalystButtonProps } from './types';

export function AIAnalystButton({
  shard,
  targetId,
  context,
  label = 'AI Analysis',
  variant = 'secondary',
  size = 'sm',
  disabled = false,
}: AIAnalystButtonProps) {
  const [isOpen, setIsOpen] = useState(false);

  const handleClick = () => {
    setIsOpen(true);
  };

  const handleClose = () => {
    setIsOpen(false);
  };

  // Build class names
  const buttonClasses = [
    'btn',
    `btn-${variant}`,
    size === 'sm' ? 'btn-sm' : size === 'lg' ? 'btn-lg' : '',
    'ai-analyst-trigger',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      <button
        className={buttonClasses}
        onClick={handleClick}
        disabled={disabled || !targetId}
        title={disabled ? 'Select an item to analyze' : label}
      >
        <Icon name="Sparkles" size={size === 'sm' ? 14 : size === 'lg' ? 18 : 16} />
        {label}
      </button>

      <AIAnalystPanel
        shard={shard}
        targetId={targetId}
        context={context}
        isOpen={isOpen}
        onClose={handleClose}
      />
    </>
  );
}

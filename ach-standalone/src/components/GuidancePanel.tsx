import { useState } from 'react';
import { STEP_GUIDANCE, GuidanceSection } from '../types';
import { ChevronDown, ChevronUp, Lightbulb } from 'lucide-react';

interface GuidancePanelProps {
  step: number;
  defaultExpanded?: boolean;
}

function GuidanceSectionItem({ section }: { section: GuidanceSection }) {
  if (section.items) {
    return (
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-blue-200">{section.heading}</h4>
        <ul className="space-y-1 pl-4">
          {section.items.map((item, idx) => (
            <li key={idx} className="text-sm text-blue-300/80 flex gap-2">
              <span className="text-blue-400">-</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (section.text) {
    return (
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-blue-200">{section.heading}</h4>
        <p className="text-sm text-blue-300/80 pl-4">{section.text}</p>
      </div>
    );
  }

  return null;
}

export function GuidancePanel({ step, defaultExpanded = true }: GuidancePanelProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const guidance = STEP_GUIDANCE[step];

  if (!guidance) return null;

  return (
    <div className="bg-blue-900/30 border border-blue-800 rounded-lg overflow-hidden">
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-blue-900/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Lightbulb className="w-5 h-5 text-blue-400 flex-shrink-0" />
          <span className="font-semibold text-blue-100">{guidance.title}</span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-blue-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-blue-400" />
        )}
      </button>

      {/* Expandable content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-blue-800/50">
          <div className="pt-3" />
          {guidance.sections.map((section, idx) => (
            <GuidanceSectionItem key={idx} section={section} />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Icon - Dynamic Lucide icon component
 *
 * Renders Lucide icons by name from shard manifests.
 * Falls back to HelpCircle if icon not found.
 */

import * as LucideIcons from 'lucide-react';
import type { LucideProps } from 'lucide-react';

interface IconProps extends LucideProps {
  name: string;
}

export function Icon({ name, ...props }: IconProps) {
  // Get icon component from Lucide
  const LucideIcon = (LucideIcons as Record<string, React.ComponentType<LucideProps>>)[name];

  if (!LucideIcon) {
    // Fallback for invalid icon names - don't crash, show placeholder
    console.warn(`Icon "${name}" not found in Lucide icons`);
    return <LucideIcons.HelpCircle {...props} />;
  }

  return <LucideIcon {...props} />;
}

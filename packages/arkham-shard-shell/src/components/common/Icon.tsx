/**
 * Icon - Dynamic Lucide icon component
 *
 * Renders Lucide icons by name from shard manifests.
 * Falls back to HelpCircle if icon not found.
 */

import * as LucideIcons from 'lucide-react';
import type { LucideProps, LucideIcon } from 'lucide-react';
import type { ComponentType } from 'react';

interface IconProps extends LucideProps {
  name: string;
  title?: string;
}

// Type for the icon lookup - only includes actual icon components
type IconLookup = Record<string, LucideIcon>;

export function Icon({ name, ...props }: IconProps) {
  // Get icon component from Lucide (cast to unknown first to avoid type overlap issues)
  const icons = LucideIcons as unknown as IconLookup;
  const LucideIcon = icons[name] as ComponentType<LucideProps> | undefined;

  if (!LucideIcon) {
    // Fallback for invalid icon names - don't crash, show placeholder
    console.warn(`Icon "${name}" not found in Lucide icons`);
    return <LucideIcons.HelpCircle {...props} />;
  }

  return <LucideIcon {...props} />;
}

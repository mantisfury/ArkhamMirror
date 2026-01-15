/**
 * Entity type icons as SVG data URIs for Cytoscape.js
 *
 * These are embedded directly as data URIs - NO external requests required.
 * This ensures 100% air-gap compatibility for offline OSINT deployments.
 *
 * Icons are based on Lucide icon paths, rendered as white strokes on
 * colored backgrounds (the background color is set via stylesheet).
 */

/**
 * Creates an SVG data URI from a path definition
 * @param pathD - The SVG path 'd' attribute(s)
 * @param color - Stroke color (default white for visibility on colored backgrounds)
 */
const createSvgDataUri = (pathD: string | string[], color: string = '#ffffff'): string => {
  const paths = Array.isArray(pathD) ? pathD : [pathD];
  const pathElements = paths.map(d => `<path d="${d}"/>`).join('');

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${pathElements}</svg>`;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

/**
 * Entity type icons as SVG data URIs
 * Keys match entity types from the backend (lowercase, normalized)
 */
export const ENTITY_ICONS: Record<string, string> = {
  // Person - User silhouette (Lucide: User)
  person: createSvgDataUri([
    'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2',
    'M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8z'
  ]),

  // Organization - Building (Lucide: Building)
  organization: createSvgDataUri([
    'M3 21h18',
    'M9 8h1',
    'M9 12h1',
    'M9 16h1',
    'M14 8h1',
    'M14 12h1',
    'M14 16h1',
    'M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16'
  ]),

  // Location - Map Pin (Lucide: MapPin)
  location: createSvgDataUri([
    'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z',
    'M12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'
  ]),

  // GPE (Geopolitical Entity) - Same as location
  gpe: createSvgDataUri([
    'M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z',
    'M12 7a3 3 0 1 0 0 6 3 3 0 0 0 0-6z'
  ]),

  // Document - File (Lucide: FileText)
  document: createSvgDataUri([
    'M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z',
    'M14 2v6h6',
    'M16 13H8',
    'M16 17H8',
    'M10 9H8'
  ]),

  // Event - Calendar (Lucide: Calendar)
  event: createSvgDataUri([
    'M8 2v4',
    'M16 2v4',
    'M3 10h18',
    'M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z'
  ]),

  // Money/Financial - Dollar Sign (Lucide: DollarSign)
  money: createSvgDataUri([
    'M12 2v20',
    'M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'
  ]),

  // Phone - Phone (Lucide: Phone)
  phone: createSvgDataUri([
    'M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z'
  ]),

  // Email - Mail (Lucide: Mail)
  email: createSvgDataUri([
    'M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z',
    'M22 6l-10 7L2 6'
  ]),

  // Claim - Target/Crosshairs (Lucide: Target)
  claim: createSvgDataUri([
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
    'M12 6a6 6 0 1 0 0 12 6 6 0 0 0 0-12z',
    'M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4z'
  ]),

  // Evidence - Check/Verified (Lucide: CheckCircle)
  evidence: createSvgDataUri([
    'M9 11l3 3L22 4',
    'M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11'
  ]),

  // Hypothesis - Lightbulb (Lucide: Lightbulb)
  hypothesis: createSvgDataUri([
    'M9 18h6',
    'M10 22h4',
    'M12 2a7 7 0 0 0-4.5 12.4c.6.5 1 1.2 1.1 2 .1.8.1 1.6.1 1.6h6.6s0-.8.1-1.6c.1-.8.5-1.5 1.1-2A7 7 0 0 0 12 2z'
  ]),

  // Account - User Circle (Lucide: UserCircle)
  account: createSvgDataUri([
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
    'M12 8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
    'M6.168 18.849A4 4 0 0 1 10 16h4a4 4 0 0 1 3.834 2.855'
  ]),

  // Vehicle - Car (Lucide: Car)
  vehicle: createSvgDataUri([
    'M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9L18 10l-3.4-5.1a2 2 0 0 0-1.7-.9H7a2 2 0 0 0-2 2v10c0 .6.4 1 1 1h2',
    'M7 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0z',
    'M15 17a2 2 0 1 0 4 0 2 2 0 0 0-4 0z'
  ]),

  // Property - Home (Lucide: Home)
  property: createSvgDataUri([
    'M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
    'M9 22V12h6v10'
  ]),

  // Product - Package (Lucide: Package)
  product: createSvgDataUri([
    'M16.5 9.4l-9-5.19',
    'M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z',
    'M3.27 6.96L12 12.01l8.73-5.05',
    'M12 22.08V12'
  ]),

  // Date/Time - Clock (Lucide: Clock)
  date: createSvgDataUri([
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
    'M12 6v6l4 2'
  ]),

  // Unknown/Fallback - Help Circle (Lucide: HelpCircle)
  unknown: createSvgDataUri([
    'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20z',
    'M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3',
    'M12 17h.01'
  ]),
};

/**
 * Entity background colors
 * These should match the existing ENTITY_TYPE_COLORS in the application
 */
export const ENTITY_COLORS: Record<string, string> = {
  person: '#4299e1',        // Blue
  organization: '#48bb78',  // Green
  location: '#ed8936',      // Orange
  gpe: '#ed8936',           // Orange (same as location)
  event: '#9f7aea',         // Purple
  document: '#f56565',      // Red
  money: '#68d391',         // Light green
  phone: '#63b3ed',         // Light blue
  email: '#63b3ed',         // Light blue
  claim: '#f59e0b',         // Amber
  evidence: '#3b82f6',      // Blue
  hypothesis: '#8b5cf6',    // Purple
  account: '#06b6d4',       // Cyan
  vehicle: '#78716c',       // Gray
  property: '#a855f7',      // Purple
  product: '#14b8a6',       // Teal
  date: '#eab308',          // Yellow
  unknown: '#718096',       // Gray
};

/**
 * Get icon for entity type (with fallback)
 */
export function getEntityIcon(type: string | undefined): string {
  if (!type) return ENTITY_ICONS.unknown;
  const normalized = type.toLowerCase().replace(/-/g, '_');
  return ENTITY_ICONS[normalized] || ENTITY_ICONS.unknown;
}

/**
 * Get color for entity type (with fallback)
 */
export function getEntityColor(type: string | undefined): string {
  if (!type) return ENTITY_COLORS.unknown;
  const normalized = type.toLowerCase().replace(/-/g, '_');
  return ENTITY_COLORS[normalized] || ENTITY_COLORS.unknown;
}

/**
 * Entity type display labels
 */
export const ENTITY_LABELS: Record<string, string> = {
  person: 'Person',
  organization: 'Organization',
  location: 'Location',
  gpe: 'Geopolitical Entity',
  event: 'Event',
  document: 'Document',
  money: 'Financial',
  phone: 'Phone',
  email: 'Email',
  claim: 'Claim',
  evidence: 'Evidence',
  hypothesis: 'Hypothesis',
  account: 'Account',
  vehicle: 'Vehicle',
  property: 'Property',
  product: 'Product',
  date: 'Date/Time',
  unknown: 'Unknown',
};

/**
 * Get display label for entity type
 */
export function getEntityLabel(type: string | undefined): string {
  if (!type) return ENTITY_LABELS.unknown;
  const normalized = type.toLowerCase().replace(/-/g, '_');
  return ENTITY_LABELS[normalized] || type;
}

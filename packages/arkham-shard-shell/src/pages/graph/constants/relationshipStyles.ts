/**
 * Relationship type styling constants for graph visualization
 *
 * Defines colors, dash patterns, and metadata for each relationship type.
 * Mirrors the backend RELATIONSHIP_TYPE_METADATA in api.py.
 */

export interface RelationshipStyle {
  category: string;
  label: string;
  color: string;
  directed: boolean;
  dash?: number[];  // SVG dash array [stroke, gap]
  width?: number;   // Line width multiplier
}

export type RelationshipCategory =
  | 'organizational'
  | 'personal'
  | 'interaction'
  | 'spatial'
  | 'temporal'
  | 'analysis'
  | 'basic';

export const RELATIONSHIP_STYLES: Record<string, RelationshipStyle> = {
  // Basic relationships
  works_for: { category: 'organizational', label: 'Works For', color: '#3b82f6', directed: true },
  affiliated_with: { category: 'organizational', label: 'Affiliated With', color: '#8b5cf6', directed: false },
  located_in: { category: 'spatial', label: 'Located In', color: '#10b981', directed: true },
  mentioned_with: { category: 'basic', label: 'Mentioned With', color: '#6b7280', directed: false },
  related_to: { category: 'basic', label: 'Related To', color: '#6b7280', directed: false },
  temporal: { category: 'temporal', label: 'Temporal', color: '#f59e0b', directed: true },
  hierarchical: { category: 'organizational', label: 'Hierarchical', color: '#3b82f6', directed: true },

  // Organizational relationships
  owns: { category: 'organizational', label: 'Owns', color: '#059669', directed: true },
  founded: { category: 'organizational', label: 'Founded', color: '#0891b2', directed: true },
  employed_by: { category: 'organizational', label: 'Employed By', color: '#3b82f6', directed: true },
  member_of: { category: 'organizational', label: 'Member Of', color: '#6366f1', directed: true },
  reports_to: { category: 'organizational', label: 'Reports To', color: '#7c3aed', directed: true },
  subsidiary_of: { category: 'organizational', label: 'Subsidiary Of', color: '#2563eb', directed: true },
  partner_of: { category: 'organizational', label: 'Partner Of', color: '#4f46e5', directed: false },

  // Personal relationships
  married_to: { category: 'personal', label: 'Married To', color: '#ec4899', directed: false },
  child_of: { category: 'personal', label: 'Child Of', color: '#f472b6', directed: true },
  parent_of: { category: 'personal', label: 'Parent Of', color: '#db2777', directed: true },
  sibling_of: { category: 'personal', label: 'Sibling Of', color: '#e879f9', directed: false },
  relative_of: { category: 'personal', label: 'Relative Of', color: '#d946ef', directed: false },
  knows: { category: 'personal', label: 'Knows', color: '#a855f7', directed: false },
  friend_of: { category: 'personal', label: 'Friend Of', color: '#c084fc', directed: false },

  // Interaction relationships
  communicated_with: { category: 'interaction', label: 'Communicated With', color: '#14b8a6', directed: false },
  met_with: { category: 'interaction', label: 'Met With', color: '#06b6d4', directed: false },
  transacted_with: { category: 'interaction', label: 'Transacted With', color: '#22c55e', directed: false },
  collaborated_with: { category: 'interaction', label: 'Collaborated With', color: '#84cc16', directed: false },

  // Spatial relationships
  visited: { category: 'spatial', label: 'Visited', color: '#f97316', directed: true },
  resides_in: { category: 'spatial', label: 'Resides In', color: '#fb923c', directed: true },
  headquartered_in: { category: 'spatial', label: 'Headquartered In', color: '#ea580c', directed: true },
  traveled_to: { category: 'spatial', label: 'Traveled To', color: '#fdba74', directed: true },

  // Temporal relationships
  preceded_by: { category: 'temporal', label: 'Preceded By', color: '#eab308', directed: true },
  followed_by: { category: 'temporal', label: 'Followed By', color: '#facc15', directed: true },
  concurrent_with: { category: 'temporal', label: 'Concurrent With', color: '#fde047', directed: false },

  // Cross-shard relationship types
  contradicts: { category: 'analysis', label: 'Contradicts', color: '#ef4444', directed: false, dash: [5, 5], width: 2 },
  supports: { category: 'analysis', label: 'Supports', color: '#22c55e', directed: false, width: 2 },
  pattern_match: { category: 'analysis', label: 'Pattern Match', color: '#a855f7', directed: false, dash: [3, 3] },
  derived_from: { category: 'analysis', label: 'Derived From', color: '#64748b', directed: true },
  evidence_for: { category: 'analysis', label: 'Evidence For', color: '#16a34a', directed: true },
  evidence_against: { category: 'analysis', label: 'Evidence Against', color: '#dc2626', directed: true },

  // Co-occurrence (default)
  co_occurrence: { category: 'basic', label: 'Co-occurrence', color: '#94a3b8', directed: false },
};

// Category metadata
export const RELATIONSHIP_CATEGORIES: Record<RelationshipCategory, { label: string; icon: string; color: string }> = {
  organizational: { label: 'Organizational', icon: 'Building2', color: '#3b82f6' },
  personal: { label: 'Personal', icon: 'Users', color: '#ec4899' },
  interaction: { label: 'Interaction', icon: 'MessageCircle', color: '#14b8a6' },
  spatial: { label: 'Spatial', icon: 'MapPin', color: '#f97316' },
  temporal: { label: 'Temporal', icon: 'Clock', color: '#eab308' },
  analysis: { label: 'Analysis', icon: 'Sparkles', color: '#a855f7' },
  basic: { label: 'Basic', icon: 'Link', color: '#6b7280' },
};

// Order for displaying categories
export const CATEGORY_ORDER: RelationshipCategory[] = [
  'organizational',
  'personal',
  'interaction',
  'spatial',
  'temporal',
  'analysis',
  'basic',
];

// Default/fallback style
export const DEFAULT_RELATIONSHIP_STYLE: RelationshipStyle = {
  category: 'basic',
  label: 'Unknown',
  color: '#6b7280',
  directed: false,
};

/**
 * Get style for a relationship type
 */
export function getRelationshipStyle(type: string | undefined): RelationshipStyle {
  if (!type) return DEFAULT_RELATIONSHIP_STYLE;
  const normalized = type.toLowerCase().replace(/-/g, '_');
  return RELATIONSHIP_STYLES[normalized] || DEFAULT_RELATIONSHIP_STYLE;
}

/**
 * Get all relationship types in a category
 */
export function getRelationshipsByCategory(category: RelationshipCategory): string[] {
  return Object.entries(RELATIONSHIP_STYLES)
    .filter(([_, style]) => style.category === category)
    .map(([type]) => type);
}

/**
 * Get unique relationship types from graph data
 */
export function extractRelationshipTypes(edges: Array<{ relationship_type?: string; type?: string }>): string[] {
  const types = new Set<string>();
  for (const edge of edges) {
    const type = edge.relationship_type || edge.type;
    if (type) {
      types.add(type.toLowerCase().replace(/-/g, '_'));
    }
  }
  return Array.from(types).sort((a, b) => {
    const styleA = RELATIONSHIP_STYLES[a];
    const styleB = RELATIONSHIP_STYLES[b];
    if (!styleA && !styleB) return a.localeCompare(b);
    if (!styleA) return 1;
    if (!styleB) return -1;
    return styleA.label.localeCompare(styleB.label);
  });
}

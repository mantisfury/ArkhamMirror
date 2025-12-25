/**
 * Type definitions for the UI Shell
 * Based on SHARD_MANIFEST_SCHEMA_v5
 */

// Shard Manifest Types
export interface ShardManifest {
  name: string;
  version: string;
  description: string;
  entry_point: string;
  api_prefix: string;
  requires_frame: string;
  navigation: NavigationConfig;
  dependencies?: DependencyConfig;
  capabilities?: string[];
  events?: EventConfig;
  state?: StateConfig;
  ui?: UIConfig;
}

export interface NavigationConfig {
  category: 'System' | 'Data' | 'Search' | 'Analysis' | 'Visualize' | 'Export';
  order: number;
  icon: string;
  label: string;
  route: string;
  badge_endpoint?: string;
  badge_type?: 'count' | 'dot';
  sub_routes?: SubRoute[];
}

export interface SubRoute {
  id: string;
  label: string;
  route: string;
  icon: string;
  badge_endpoint?: string;
  badge_type?: 'count' | 'dot';
}

export interface DependencyConfig {
  services?: string[];
  optional?: string[];
  shards?: string[];
}

export interface EventConfig {
  publishes?: string[];
  subscribes?: string[];
}

export interface StateConfig {
  strategy: 'url' | 'local' | 'session' | 'none';
  url_params?: string[];
  local_keys?: string[];
}

// UI Configuration
export interface UIConfig {
  has_custom_ui: boolean;
  id_field?: string;
  selectable?: boolean;
  list_endpoint?: string;
  detail_endpoint?: string;
  list_filters?: FilterConfig[];
  list_columns?: ColumnConfig[];
  bulk_actions?: BulkAction[];
  row_actions?: RowAction[];
  primary_action?: ActionConfig;
  actions?: ActionConfig[];
}

// Filter Types
export interface FilterConfig {
  name: string;
  type: 'search' | 'select' | 'multi_select' | 'boolean' | 'date' | 'date_range' | 'number_range';
  label: string;
  param?: string;
  param_start?: string;
  param_end?: string;
  param_min?: string;
  param_max?: string;
  default?: string | number | boolean;
  options?: SelectOption[];
}

export interface SelectOption {
  value: string;
  label: string;
}

// Column Types
export interface ColumnConfig {
  field: string;
  label: string;
  type: 'text' | 'link' | 'number' | 'date' | 'badge' | 'boolean';
  link_route?: string;
  format?: 'integer' | 'decimal' | 'percent' | 'absolute' | 'relative';
  width?: string;
  sortable?: boolean;
  default_sort?: 'asc' | 'desc';
}

// Action Types
export interface BulkAction {
  label: string;
  endpoint: string;
  method: 'POST' | 'DELETE' | 'PUT' | 'PATCH';
  confirm?: boolean;
  confirm_message?: string;
  style?: 'default' | 'primary' | 'danger';
  icon?: string;
}

export interface RowAction {
  label: string;
  type: 'link' | 'api';
  route?: string;
  endpoint?: string;
  method?: 'POST' | 'DELETE' | 'PUT' | 'PATCH';
  confirm?: boolean;
  confirm_message?: string;
  style?: 'default' | 'primary' | 'danger';
  icon?: string;
}

export interface ActionConfig {
  label: string;
  endpoint: string;
  method: 'POST' | 'PUT' | 'PATCH';
  description?: string;
  fields: FormFieldConfig[];
}

export interface FormFieldConfig {
  name: string;
  type: 'text' | 'textarea' | 'number' | 'email' | 'select';
  label: string;
  required?: boolean;
  min?: number;
  max?: number;
  pattern?: string;
  error_message?: string;
  default?: string | number;
  options?: SelectOption[];
}

// API Response Types
export interface PaginatedResponse<T = Record<string, unknown>> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface BulkActionResponse {
  success: boolean;
  processed: number;
  failed: number;
  errors: string[];
  message: string;
}

export interface BadgeInfo {
  count: number;
  type: 'count' | 'dot';
}

export interface BadgeState {
  [key: string]: BadgeInfo;
}

// Toast Types
export interface Toast {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  duration: number;
}

export interface ToastOptions {
  duration?: number;
}

// Confirm Dialog Types
export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'default' | 'danger';
}

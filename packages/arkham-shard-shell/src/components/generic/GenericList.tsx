/**
 * GenericList - Data-driven list component
 *
 * Renders a list/table with filters, pagination, and actions
 * based on manifest UI configuration.
 *
 * Shell Invariants:
 * - Non-authoritative: Only renders what API provides
 * - Surfaces errors: Displays API errors to user
 * - Minimal logic: No business logic, just rendering
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useFetch, usePageSize } from '../../hooks';
import { useToast } from '../../context/ToastContext';
import { useConfirm } from '../../context/ConfirmContext';
import { Icon } from '../common/Icon';
import { LoadingSkeleton } from '../common/LoadingSkeleton';
import type {
  UIConfig,
  ColumnConfig,
  FilterConfig,
  BulkAction,
  RowAction,
  PaginatedResponse,
} from '../../types';

interface GenericListProps {
  apiPrefix: string;
  ui: UIConfig;
}

type SortDirection = 'asc' | 'desc' | null;

interface SortState {
  field: string | null;
  direction: SortDirection;
}

export function GenericList({ apiPrefix, ui }: GenericListProps) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { toast } = useToast();
  const confirm = useConfirm();

  // Get page size from settings
  const defaultPageSize = usePageSize();

  // State
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLoading, setBulkLoading] = useState(false);

  // Parse URL params for filters and pagination
  const page = parseInt(searchParams.get('page') || '1', 10);
  const pageSize = parseInt(searchParams.get('page_size') || String(defaultPageSize), 10);

  // Sort state from URL
  const sortState: SortState = useMemo(() => {
    const sortParam = searchParams.get('sort');
    if (!sortParam) {
      // Check for default sort from columns
      const defaultSortCol = ui.list_columns?.find(c => c.default_sort);
      if (defaultSortCol) {
        return { field: defaultSortCol.field, direction: defaultSortCol.default_sort || 'asc' };
      }
      return { field: null, direction: null };
    }
    const isDesc = sortParam.startsWith('-');
    return {
      field: isDesc ? sortParam.slice(1) : sortParam,
      direction: isDesc ? 'desc' : 'asc',
    };
  }, [searchParams, ui.list_columns]);

  // Build API URL with all params
  const apiUrl = useMemo(() => {
    if (!ui.list_endpoint) return null;

    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(pageSize));

    // Add sort
    if (sortState.field) {
      params.set('sort', sortState.direction === 'desc' ? `-${sortState.field}` : sortState.field);
    }

    // Add filters from URL
    ui.list_filters?.forEach(filter => {
      const paramName = filter.param || filter.name;
      const value = searchParams.get(paramName);
      if (value) {
        params.set(paramName, value);
      }
      // Handle range filters
      if (filter.param_start) {
        const startVal = searchParams.get(filter.param_start);
        if (startVal) params.set(filter.param_start, startVal);
      }
      if (filter.param_end) {
        const endVal = searchParams.get(filter.param_end);
        if (endVal) params.set(filter.param_end, endVal);
      }
      if (filter.param_min) {
        const minVal = searchParams.get(filter.param_min);
        if (minVal) params.set(filter.param_min, minVal);
      }
      if (filter.param_max) {
        const maxVal = searchParams.get(filter.param_max);
        if (maxVal) params.set(filter.param_max, maxVal);
      }
    });

    return `${apiPrefix}${ui.list_endpoint}?${params.toString()}`;
  }, [apiPrefix, ui.list_endpoint, ui.list_filters, page, pageSize, sortState, searchParams]);

  // Fetch data
  const { data, loading, error, refetch } = useFetch<PaginatedResponse>(apiUrl);

  // Clear selection when data changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [data]);

  // Update URL params
  const updateParams = useCallback((updates: Record<string, string | null>) => {
    const newParams = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null || value === '') {
        newParams.delete(key);
      } else {
        newParams.set(key, value);
      }
    });
    setSearchParams(newParams);
  }, [searchParams, setSearchParams]);

  // Handlers
  const handleSort = useCallback((field: string) => {
    const column = ui.list_columns?.find(c => c.field === field);
    if (!column?.sortable) return;

    let newDirection: SortDirection;
    if (sortState.field !== field) {
      newDirection = 'asc';
    } else if (sortState.direction === 'asc') {
      newDirection = 'desc';
    } else {
      newDirection = null;
    }

    if (newDirection) {
      updateParams({
        sort: newDirection === 'desc' ? `-${field}` : field,
        page: '1', // Reset to first page on sort change
      });
    } else {
      updateParams({ sort: null, page: '1' });
    }
  }, [sortState, ui.list_columns, updateParams]);

  const handlePageChange = useCallback((newPage: number) => {
    updateParams({ page: String(newPage) });
  }, [updateParams]);

  const handleSelectAll = useCallback((checked: boolean) => {
    if (checked && data?.items) {
      const idField = ui.id_field || 'id';
      setSelectedIds(new Set(data.items.map(item => String(item[idField]))));
    } else {
      setSelectedIds(new Set());
    }
  }, [data, ui.id_field]);

  const handleSelectRow = useCallback((id: string, checked: boolean) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
  }, []);

  const handleBulkAction = useCallback(async (action: BulkAction) => {
    if (selectedIds.size === 0) {
      toast.warning('No items selected');
      return;
    }

    if (action.confirm) {
      const confirmed = await confirm({
        title: action.label,
        message: action.confirm_message || `Are you sure you want to ${action.label.toLowerCase()} ${selectedIds.size} item(s)?`,
        variant: action.style === 'danger' ? 'danger' : 'default',
      });
      if (!confirmed) return;
    }

    setBulkLoading(true);
    try {
      const response = await fetch(`${apiPrefix}${action.endpoint}`, {
        method: action.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: Array.from(selectedIds) }),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || result.message || 'Bulk action failed');
      }

      toast.success(result.message || `${action.label} completed`);
      setSelectedIds(new Set());
      refetch();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Bulk action failed');
    } finally {
      setBulkLoading(false);
    }
  }, [selectedIds, apiPrefix, toast, confirm, refetch]);

  const handleRowAction = useCallback(async (action: RowAction, item: Record<string, unknown>) => {
    const idField = ui.id_field || 'id';
    const itemId = String(item[idField]);

    if (action.type === 'link' && action.route) {
      // Navigate to route, replacing {id} placeholder
      const route = action.route.replace('{id}', itemId);
      navigate(route);
      return;
    }

    if (action.type === 'api' && action.endpoint) {
      if (action.confirm) {
        const confirmed = await confirm({
          title: action.label,
          message: action.confirm_message || `Are you sure you want to ${action.label.toLowerCase()} this item?`,
          variant: action.style === 'danger' ? 'danger' : 'default',
        });
        if (!confirmed) return;
      }

      try {
        const endpoint = action.endpoint.replace('{id}', itemId);
        const response = await fetch(`${apiPrefix}${endpoint}`, {
          method: action.method || 'POST',
          headers: { 'Content-Type': 'application/json' },
        });

        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.detail || result.message || 'Action failed');
        }

        toast.success(result.message || `${action.label} completed`);
        refetch();
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Action failed');
      }
    }
  }, [apiPrefix, ui.id_field, navigate, toast, confirm, refetch]);

  // Render loading state
  if (loading && !data) {
    return <LoadingSkeleton type="list" />;
  }

  // Render error state
  if (error && !data) {
    return (
      <div className="generic-list-error">
        <Icon name="AlertCircle" size={48} />
        <h2>Failed to load data</h2>
        <p>{error.message}</p>
        <button className="btn btn-primary" onClick={() => refetch()}>
          <Icon name="RefreshCw" size={16} />
          Retry
        </button>
      </div>
    );
  }

  const items = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize);
  const idField = ui.id_field || 'id';
  const selectable = ui.selectable !== false;

  return (
    <div className="generic-list">
      {/* Filters */}
      {ui.list_filters && ui.list_filters.length > 0 && (
        <GenericListFilters
          filters={ui.list_filters}
          searchParams={searchParams}
          onFilterChange={updateParams}
        />
      )}

      {/* Toolbar */}
      <div className="generic-list-toolbar">
        <div className="toolbar-left">
          {selectable && selectedIds.size > 0 && (
            <span className="selection-count">
              {selectedIds.size} selected
            </span>
          )}

          {/* Bulk Actions */}
          {selectable && ui.bulk_actions && ui.bulk_actions.length > 0 && selectedIds.size > 0 && (
            <div className="bulk-actions">
              {ui.bulk_actions.map((action, idx) => (
                <button
                  key={idx}
                  className={`btn btn-sm ${action.style === 'danger' ? 'btn-danger' : action.style === 'primary' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleBulkAction(action)}
                  disabled={bulkLoading}
                >
                  {action.icon && <Icon name={action.icon} size={14} />}
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="toolbar-right">
          {/* Total count */}
          <span className="total-count">{total} items</span>

          {/* Refresh */}
          <button
            className="btn btn-icon"
            onClick={() => refetch()}
            disabled={loading}
            title="Refresh"
          >
            <Icon name={loading ? 'Loader2' : 'RefreshCw'} size={16} className={loading ? 'spin' : undefined} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="generic-list-table-container">
        <table className="generic-list-table">
          <thead>
            <tr>
              {selectable && (
                <th className="col-select">
                  <input
                    type="checkbox"
                    checked={items.length > 0 && selectedIds.size === items.length}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    aria-label="Select all"
                  />
                </th>
              )}
              {ui.list_columns?.map(column => (
                <th
                  key={column.field}
                  className={`col-${column.type} ${column.sortable ? 'sortable' : ''}`}
                  style={{ width: column.width }}
                  onClick={() => column.sortable && handleSort(column.field)}
                >
                  <span className="th-content">
                    {column.label}
                    {column.sortable && (
                      <span className="sort-indicator">
                        {sortState.field === column.field ? (
                          <Icon
                            name={sortState.direction === 'desc' ? 'ChevronDown' : 'ChevronUp'}
                            size={14}
                          />
                        ) : (
                          <Icon name="ChevronsUpDown" size={14} className="sort-inactive" />
                        )}
                      </span>
                    )}
                  </span>
                </th>
              ))}
              {ui.row_actions && ui.row_actions.length > 0 && (
                <th className="col-actions">Actions</th>
              )}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={100} className="empty-row">
                  <Icon name="Inbox" size={32} />
                  <span>No items found</span>
                </td>
              </tr>
            ) : (
              items.map(item => {
                const itemId = String(item[idField]);
                return (
                  <tr key={itemId} className={selectedIds.has(itemId) ? 'selected' : ''}>
                    {selectable && (
                      <td className="col-select">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(itemId)}
                          onChange={(e) => handleSelectRow(itemId, e.target.checked)}
                          aria-label={`Select item ${itemId}`}
                        />
                      </td>
                    )}
                    {ui.list_columns?.map(column => (
                      <td key={column.field} className={`col-${column.type}`}>
                        <CellRenderer column={column} value={item[column.field]} item={item} />
                      </td>
                    ))}
                    {ui.row_actions && ui.row_actions.length > 0 && (
                      <td className="col-actions">
                        <div className="row-actions">
                          {ui.row_actions.map((action, idx) => (
                            <button
                              key={idx}
                              className={`btn btn-icon btn-sm ${action.style === 'danger' ? 'btn-danger' : ''}`}
                              onClick={() => handleRowAction(action, item)}
                              title={action.label}
                            >
                              {action.icon ? <Icon name={action.icon} size={14} /> : action.label}
                            </button>
                          ))}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="generic-list-pagination">
          <button
            className="btn btn-icon"
            onClick={() => handlePageChange(1)}
            disabled={page === 1}
            title="First page"
          >
            <Icon name="ChevronsLeft" size={16} />
          </button>
          <button
            className="btn btn-icon"
            onClick={() => handlePageChange(page - 1)}
            disabled={page === 1}
            title="Previous page"
          >
            <Icon name="ChevronLeft" size={16} />
          </button>

          <span className="page-info">
            Page {page} of {totalPages}
          </span>

          <button
            className="btn btn-icon"
            onClick={() => handlePageChange(page + 1)}
            disabled={page >= totalPages}
            title="Next page"
          >
            <Icon name="ChevronRight" size={16} />
          </button>
          <button
            className="btn btn-icon"
            onClick={() => handlePageChange(totalPages)}
            disabled={page >= totalPages}
            title="Last page"
          >
            <Icon name="ChevronsRight" size={16} />
          </button>
        </div>
      )}
    </div>
  );
}

// ==== Sub-components ====

interface GenericListFiltersProps {
  filters: FilterConfig[];
  searchParams: URLSearchParams;
  onFilterChange: (updates: Record<string, string | null>) => void;
}

function GenericListFilters({ filters, searchParams, onFilterChange }: GenericListFiltersProps) {
  return (
    <div className="generic-list-filters">
      {filters.map(filter => (
        <FilterInput
          key={filter.name}
          filter={filter}
          value={searchParams.get(filter.param || filter.name) || ''}
          onChange={(value) => onFilterChange({ [filter.param || filter.name]: value || null, page: '1' })}
        />
      ))}
    </div>
  );
}

interface FilterInputProps {
  filter: FilterConfig;
  value: string;
  onChange: (value: string) => void;
}

function FilterInput({ filter, value, onChange }: FilterInputProps) {
  switch (filter.type) {
    case 'search':
      return (
        <div className="filter-input filter-search">
          <Icon name="Search" size={16} />
          <input
            type="text"
            placeholder={filter.label}
            value={value}
            onChange={(e) => onChange(e.target.value)}
          />
          {value && (
            <button className="clear-btn" onClick={() => onChange('')}>
              <Icon name="X" size={14} />
            </button>
          )}
        </div>
      );

    case 'select':
      return (
        <div className="filter-input filter-select">
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            aria-label={filter.label}
          >
            <option value="">{filter.label}</option>
            {filter.options?.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      );

    case 'boolean':
      return (
        <div className="filter-input filter-boolean">
          <label>
            <input
              type="checkbox"
              checked={value === 'true'}
              onChange={(e) => onChange(e.target.checked ? 'true' : '')}
            />
            {filter.label}
          </label>
        </div>
      );

    default:
      return null;
  }
}

interface CellRendererProps {
  column: ColumnConfig;
  value: unknown;
  item: Record<string, unknown>;
}

function CellRenderer({ column, value, item }: CellRendererProps) {
  if (value === null || value === undefined) {
    return <span className="cell-empty">-</span>;
  }

  switch (column.type) {
    case 'link':
      if (column.link_route) {
        const idField = 'id'; // Default, could be configurable
        const route = column.link_route.replace('{id}', String(item[idField]));
        return <a href={route}>{String(value)}</a>;
      }
      return <span>{String(value)}</span>;

    case 'number':
      const num = Number(value);
      let formatted: string;
      switch (column.format) {
        case 'integer':
          formatted = Math.round(num).toLocaleString();
          break;
        case 'decimal':
          formatted = num.toFixed(2);
          break;
        case 'percent':
          formatted = `${(num * 100).toFixed(1)}%`;
          break;
        default:
          formatted = num.toLocaleString();
      }
      return <span className="cell-number">{formatted}</span>;

    case 'date':
      const date = new Date(String(value));
      if (isNaN(date.getTime())) {
        return <span className="cell-empty">Invalid date</span>;
      }
      switch (column.format) {
        case 'relative':
          return <span className="cell-date">{formatRelativeTime(date)}</span>;
        case 'absolute':
        default:
          return <span className="cell-date">{date.toLocaleString()}</span>;
      }

    case 'badge':
      return <span className={`cell-badge badge-${String(value).toLowerCase()}`}>{String(value)}</span>;

    case 'boolean':
      return (
        <span className={`cell-boolean ${value ? 'true' : 'false'}`}>
          <Icon name={value ? 'Check' : 'X'} size={16} />
        </span>
      );

    case 'text':
    default:
      return <span>{String(value)}</span>;
  }
}

// Helper function
function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString();
}

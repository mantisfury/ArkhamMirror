/**
 * AnnotationPanel - Manage and display graph annotations
 *
 * Features:
 * - List all annotations (notes, labels, highlights)
 * - Add new annotations via modal
 * - Edit existing annotations
 * - Delete annotations
 * - Filter by type
 */

import { useState, useCallback, useEffect } from 'react';
import { Icon } from '../../../components/common/Icon';
import { apiDelete, apiGet, apiPost, apiPut } from '../../../utils/api';

export type AnnotationType = 'note' | 'label' | 'highlight' | 'group';

export interface Annotation {
  id: string;
  graph_id: string;
  annotation_type: AnnotationType;
  content: string;
  node_id: string | null;
  edge_source: string | null;
  edge_target: string | null;
  color: string | null;
  position_x: number | null;
  position_y: number | null;
  created_at: string;
  updated_at: string;
}

export interface AnnotationPanelProps {
  projectId: string;
  graphId: string | null;
  annotations: Annotation[];
  onRefresh: () => Promise<void>;
  onAnnotationClick?: (annotation: Annotation) => void;
  onAddAnnotation?: (type: AnnotationType, nodeId?: string, edgeKey?: { source: string; target: string }) => void;
  loading?: boolean;
}

interface AnnotationModalState {
  visible: boolean;
  mode: 'add' | 'edit';
  type: AnnotationType;
  annotation: Annotation | null;
  nodeId: string | null;
  edgeKey: { source: string; target: string } | null;
}

export function AnnotationPanel({
  projectId,
  graphId,
  annotations,
  onRefresh,
  onAnnotationClick,
  loading = false,
}: AnnotationPanelProps) {
  const [filterType, setFilterType] = useState<AnnotationType | 'all'>('all');
  const [modal, setModal] = useState<AnnotationModalState>({
    visible: false,
    mode: 'add',
    type: 'note',
    annotation: null,
    nodeId: null,
    edgeKey: null,
  });
  const [content, setContent] = useState('');
  const [color, setColor] = useState('#3b82f6');
  const [saving, setSaving] = useState(false);

  // Filter annotations
  const filteredAnnotations = filterType === 'all'
    ? annotations
    : annotations.filter(a => a.annotation_type === filterType);

  // Group annotations by type for stats
  const stats = {
    notes: annotations.filter(a => a.annotation_type === 'note').length,
    labels: annotations.filter(a => a.annotation_type === 'label').length,
    highlights: annotations.filter(a => a.annotation_type === 'highlight').length,
    groups: annotations.filter(a => a.annotation_type === 'group').length,
  };

  // Open modal for adding new annotation
  const openAddModal = useCallback((
    type: AnnotationType,
    nodeId?: string | null,
    edgeKey?: { source: string; target: string } | null
  ) => {
    setContent('');
    setColor('#3b82f6');
    setModal({
      visible: true,
      mode: 'add',
      type,
      annotation: null,
      nodeId: nodeId || null,
      edgeKey: edgeKey || null,
    });
  }, []);

  // Open modal for editing existing annotation
  const openEditModal = useCallback((annotation: Annotation) => {
    setContent(annotation.content);
    setColor(annotation.color || '#3b82f6');
    setModal({
      visible: true,
      mode: 'edit',
      type: annotation.annotation_type,
      annotation,
      nodeId: annotation.node_id,
      edgeKey: annotation.edge_source && annotation.edge_target
        ? { source: annotation.edge_source, target: annotation.edge_target }
        : null,
    });
  }, []);

  // Close modal
  const closeModal = useCallback(() => {
    setModal(prev => ({ ...prev, visible: false }));
    setContent('');
    setColor('#3b82f6');
  }, []);

  // Save annotation (add or edit)
  const saveAnnotation = useCallback(async () => {
    if (!graphId || !content.trim()) return;

    setSaving(true);
    try {
      if (modal.mode === 'add') {
        await apiPost('/api/graph/annotations', {
          project_id: projectId,
          graph_id: graphId,
          annotation_type: modal.type,
          content: content.trim(),
          node_id: modal.nodeId,
          edge_source: modal.edgeKey?.source,
          edge_target: modal.edgeKey?.target,
          color: modal.type === 'highlight' ? color : null,
        });
      } else if (modal.annotation) {
        await apiPut(`/api/graph/annotations/${modal.annotation.id}`, {
          content: content.trim(),
          color: modal.type === 'highlight' ? color : modal.annotation.color,
        });
      }

      await onRefresh();
      closeModal();
    } catch (error) {
      console.error('Error saving annotation:', error);
    } finally {
      setSaving(false);
    }
  }, [projectId, graphId, modal, content, color, onRefresh, closeModal]);

  // Delete annotation
  const deleteAnnotation = useCallback(async (annotationId: string) => {
    if (!window.confirm('Delete this annotation?')) return;

    try {
      await apiDelete(`/api/graph/annotations/${annotationId}`);

      await onRefresh();
    } catch (error) {
      console.error('Error deleting annotation:', error);
    }
  }, [onRefresh]);

  // Get icon for annotation type
  const getTypeIcon = (type: AnnotationType) => {
    switch (type) {
      case 'note': return 'StickyNote';
      case 'label': return 'Tag';
      case 'highlight': return 'Highlighter';
      case 'group': return 'Group';
      default: return 'FileText';
    }
  };

  // Get target description
  const getTargetDescription = (annotation: Annotation) => {
    if (annotation.node_id) {
      return `Node: ${annotation.node_id.slice(0, 8)}...`;
    }
    if (annotation.edge_source && annotation.edge_target) {
      return `Edge: ${annotation.edge_source.slice(0, 6)}→${annotation.edge_target.slice(0, 6)}`;
    }
    return 'Graph-level';
  };

  return (
    <div className="annotation-panel">
      {/* Header */}
      <div className="annotation-header">
        <h4>Annotations</h4>
        <button
          className="btn btn-sm btn-icon"
          onClick={() => onRefresh()}
          disabled={loading}
          title="Refresh annotations"
        >
          <Icon name={loading ? 'Loader2' : 'RefreshCw'} size={14} className={loading ? 'spin' : ''} />
        </button>
      </div>

      {/* Stats */}
      <div className="annotation-stats">
        <span className="stat" title="Notes">
          <Icon name="StickyNote" size={12} />
          {stats.notes}
        </span>
        <span className="stat" title="Labels">
          <Icon name="Tag" size={12} />
          {stats.labels}
        </span>
        <span className="stat" title="Highlights">
          <Icon name="Highlighter" size={12} />
          {stats.highlights}
        </span>
        <span className="stat" title="Groups">
          <Icon name="Group" size={12} />
          {stats.groups}
        </span>
      </div>

      {/* Filter */}
      <div className="annotation-filter">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as AnnotationType | 'all')}
          className="filter-select"
        >
          <option value="all">All Types ({annotations.length})</option>
          <option value="note">Notes ({stats.notes})</option>
          <option value="label">Labels ({stats.labels})</option>
          <option value="highlight">Highlights ({stats.highlights})</option>
          <option value="group">Groups ({stats.groups})</option>
        </select>
      </div>

      {/* Add Buttons */}
      <div className="annotation-add-buttons">
        <button
          className="btn btn-sm btn-secondary"
          onClick={() => openAddModal('note')}
          disabled={!graphId}
          title="Add a note"
        >
          <Icon name="StickyNote" size={14} />
          Note
        </button>
        <button
          className="btn btn-sm btn-secondary"
          onClick={() => openAddModal('label')}
          disabled={!graphId}
          title="Add a label"
        >
          <Icon name="Tag" size={14} />
          Label
        </button>
        <button
          className="btn btn-sm btn-secondary"
          onClick={() => openAddModal('highlight')}
          disabled={!graphId}
          title="Add a highlight"
        >
          <Icon name="Highlighter" size={14} />
          Highlight
        </button>
      </div>

      {/* Annotations List */}
      <div className="annotation-list">
        {filteredAnnotations.length === 0 ? (
          <div className="annotation-empty">
            <Icon name="MessageSquare" size={24} />
            <p>No annotations yet</p>
            <p className="hint">Add notes, labels, or highlights to your graph</p>
          </div>
        ) : (
          filteredAnnotations.map(annotation => (
            <div
              key={annotation.id}
              className={`annotation-item annotation-type-${annotation.annotation_type}`}
              onClick={() => onAnnotationClick?.(annotation)}
              style={annotation.color ? { borderLeftColor: annotation.color } : undefined}
            >
              <div className="annotation-item-header">
                <Icon name={getTypeIcon(annotation.annotation_type)} size={14} />
                <span className="annotation-target">{getTargetDescription(annotation)}</span>
                <div className="annotation-actions">
                  <button
                    className="btn btn-icon btn-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      openEditModal(annotation);
                    }}
                    title="Edit"
                  >
                    <Icon name="Pencil" size={12} />
                  </button>
                  <button
                    className="btn btn-icon btn-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteAnnotation(annotation.id);
                    }}
                    title="Delete"
                  >
                    <Icon name="Trash2" size={12} />
                  </button>
                </div>
              </div>
              <div className="annotation-content">
                {annotation.content}
              </div>
              <div className="annotation-meta">
                {new Date(annotation.created_at).toLocaleDateString()}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Add/Edit Modal */}
      {modal.visible && (
        <div className="annotation-modal-overlay" onClick={closeModal}>
          <div className="annotation-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                {modal.mode === 'add' ? 'Add' : 'Edit'}{' '}
                {modal.type.charAt(0).toUpperCase() + modal.type.slice(1)}
              </h3>
              <button className="btn btn-icon" onClick={closeModal}>
                <Icon name="X" size={16} />
              </button>
            </div>
            <div className="modal-body">
              {modal.nodeId && (
                <div className="modal-info">
                  <Icon name="GitCommit" size={14} />
                  Target: Node {modal.nodeId.slice(0, 12)}...
                </div>
              )}
              {modal.edgeKey && (
                <div className="modal-info">
                  <Icon name="ArrowRight" size={14} />
                  Target: Edge {modal.edgeKey.source.slice(0, 6)} → {modal.edgeKey.target.slice(0, 6)}
                </div>
              )}
              {!modal.nodeId && !modal.edgeKey && (
                <div className="modal-info">
                  <Icon name="Layout" size={14} />
                  Target: Graph-level
                </div>
              )}

              <div className="form-group">
                <label>Content</label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder={`Enter ${modal.type} content...`}
                  rows={modal.type === 'note' ? 4 : 2}
                  autoFocus
                />
              </div>

              {modal.type === 'highlight' && (
                <div className="form-group">
                  <label>Color</label>
                  <div className="color-picker">
                    {['#ef4444', '#f59e0b', '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899'].map(c => (
                      <button
                        key={c}
                        className={`color-option ${color === c ? 'selected' : ''}`}
                        style={{ backgroundColor: c }}
                        onClick={() => setColor(c)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={closeModal}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={saveAnnotation}
                disabled={saving || !content.trim()}
              >
                {saving ? (
                  <>
                    <Icon name="Loader2" size={14} className="spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Icon name="Check" size={14} />
                    {modal.mode === 'add' ? 'Add' : 'Save'}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Hook for managing annotations
 */
export function useAnnotations(projectId: string, graphId: string | null) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [loading, setLoading] = useState(false);

  // Load annotations from backend
  const loadAnnotations = useCallback(async () => {
    if (!graphId) {
      setAnnotations([]);
      return;
    }

    setLoading(true);
    try {
      const data = await apiGet<{ annotations?: Annotation[] }>(`/api/graph/annotations/${projectId}?graph_id=${graphId}`);
      setAnnotations(Array.isArray(data.annotations) ? data.annotations : []);
    } catch (error) {
      console.error('Error loading annotations:', error);
      setAnnotations([]);
    } finally {
      setLoading(false);
    }
  }, [projectId, graphId]);

  // Load on mount and when graphId changes
  useEffect(() => {
    loadAnnotations();
  }, [loadAnnotations]);

  return {
    annotations,
    loading,
    refresh: loadAnnotations,
  };
}

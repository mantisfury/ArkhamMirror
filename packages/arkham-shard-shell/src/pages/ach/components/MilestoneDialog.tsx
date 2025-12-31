/**
 * MilestoneDialog - Add/Edit milestone modal
 */

import { useState, useEffect } from 'react';
import { Icon } from '../../../components/common/Icon';

interface Milestone {
  id: string;
  description: string;
  hypothesis_id: string;
  hypothesis_label?: string;
  expected_by: string | null;
  observed: -1 | 0 | 1;
  observation_notes: string;
  created_at: string;
}

interface MilestoneDialogProps {
  milestone?: Milestone | null;
  hypotheses: { id: string; title: string }[];
  onSave: (milestone: Partial<Milestone>) => void;
  onClose: () => void;
}

export function MilestoneDialog({
  milestone,
  hypotheses,
  onSave,
  onClose,
}: MilestoneDialogProps) {
  const isEdit = !!milestone;
  const [description, setDescription] = useState(milestone?.description || '');
  const [hypothesisId, setHypothesisId] = useState(milestone?.hypothesis_id || (hypotheses[0]?.id || ''));
  const [expectedBy, setExpectedBy] = useState(milestone?.expected_by?.split('T')[0] || '');
  const [observationNotes, setObservationNotes] = useState(milestone?.observation_notes || '');
  const [status, setStatus] = useState<-1 | 0 | 1>(milestone?.observed ?? 0);

  useEffect(() => {
    if (milestone) {
      setDescription(milestone.description);
      setHypothesisId(milestone.hypothesis_id);
      setExpectedBy(milestone.expected_by?.split('T')[0] || '');
      setObservationNotes(milestone.observation_notes || '');
      setStatus(milestone.observed);
    }
  }, [milestone]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim()) return;

    const hypTitle = hypotheses.find(h => h.id === hypothesisId)?.title || 'General';
    onSave({
      id: milestone?.id || `milestone-${Date.now()}`,
      description: description.trim(),
      hypothesis_id: hypothesisId,
      hypothesis_label: hypTitle,
      expected_by: expectedBy ? new Date(expectedBy).toISOString() : null,
      observed: status,
      observation_notes: observationNotes.trim(),
      created_at: milestone?.created_at || new Date().toISOString(),
    });
  };

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div className="dialog dialog-md" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>{isEdit ? 'Edit Milestone' : 'Add Milestone'}</h2>
          <button className="btn btn-icon" onClick={onClose}>
            <Icon name="X" size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <p className="dialog-description">
            What future event indicates a hypothesis is coming true?
          </p>

          <div className="form-group">
            <label htmlFor="description">Description</label>
            <textarea
              id="description"
              className="form-textarea"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="E.g., 'If H1 is true, we expect to see X by next month'"
              rows={3}
              autoFocus
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="hypothesis">Related Hypothesis</label>
            <select
              id="hypothesis"
              className="form-select"
              value={hypothesisId}
              onChange={(e) => setHypothesisId(e.target.value)}
            >
              {hypotheses.length === 0 ? (
                <option value="">No hypotheses available</option>
              ) : (
                hypotheses.map((h, i) => (
                  <option key={h.id} value={h.id}>
                    H{i + 1}: {h.title}
                  </option>
                ))
              )}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="expectedBy">Expected By (Optional)</label>
              <input
                id="expectedBy"
                type="date"
                className="form-input"
                value={expectedBy}
                onChange={(e) => setExpectedBy(e.target.value)}
              />
            </div>

            {isEdit && (
              <div className="form-group">
                <label htmlFor="status">Status</label>
                <select
                  id="status"
                  className="form-select"
                  value={status}
                  onChange={(e) => setStatus(parseInt(e.target.value) as -1 | 0 | 1)}
                >
                  <option value={0}>Pending</option>
                  <option value={1}>Observed</option>
                  <option value={-1}>Contradicted</option>
                </select>
              </div>
            )}
          </div>

          {isEdit && (
            <div className="form-group">
              <label htmlFor="notes">Observation Notes</label>
              <textarea
                id="notes"
                className="form-textarea"
                value={observationNotes}
                onChange={(e) => setObservationNotes(e.target.value)}
                placeholder="Notes about observations or why status changed..."
                rows={2}
              />
            </div>
          )}

          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={!description.trim()}
            >
              {isEdit ? 'Save Changes' : 'Add Milestone'}
            </button>
          </div>
        </form>

        <style>{`
          .form-group {
            margin-bottom: 1rem;
          }
          .form-group label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            color: #d1d5db;
            margin-bottom: 0.375rem;
          }
          .form-textarea,
          .form-input,
          .form-select {
            width: 100%;
            padding: 0.625rem 0.75rem;
            background: #111827;
            border: 1px solid #374151;
            border-radius: 0.375rem;
            color: #f9fafb;
            font-size: 0.9375rem;
          }
          .form-textarea:focus,
          .form-input:focus,
          .form-select:focus {
            outline: none;
            border-color: #6366f1;
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
          }
          .form-textarea::placeholder,
          .form-input::placeholder {
            color: #6b7280;
          }
          .form-select {
            appearance: none;
            background-image: url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%239ca3af' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e");
            background-position: right 0.5rem center;
            background-repeat: no-repeat;
            background-size: 1.5em 1.5em;
            padding-right: 2.5rem;
          }
          .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
          }
          .dialog-description {
            font-size: 0.875rem;
            color: #9ca3af;
            margin: 0 0 1.25rem 0;
          }
        `}</style>
      </div>
    </div>
  );
}

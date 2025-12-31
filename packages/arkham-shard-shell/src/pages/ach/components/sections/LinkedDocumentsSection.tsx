/**
 * LinkedDocumentsSection - Manage documents linked to an ACH matrix
 *
 * Allows users to:
 * - View currently linked documents
 * - Add documents from the corpus
 * - Remove linked documents
 *
 * Linked documents are used as the default scope for corpus search.
 */

import { useState, useEffect, useCallback } from 'react';
import { Icon } from '../../../../components/common/Icon';
import { useToast } from '../../../../context/ToastContext';
import * as achApi from '../../api';

interface LinkedDocumentsSectionProps {
  matrixId: string;
  linkedDocumentIds: string[];
  onDocumentsChanged: () => void;
}

interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
}

interface DocumentsResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
}

export function LinkedDocumentsSection({
  matrixId,
  linkedDocumentIds,
  onDocumentsChanged,
}: LinkedDocumentsSectionProps) {
  const { toast } = useToast();

  const [availableDocuments, setAvailableDocuments] = useState<Document[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [unlinking, setUnlinking] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);

  // Fetch available documents from the documents API
  const fetchAvailableDocuments = useCallback(async () => {
    setLoadingDocs(true);
    try {
      const response = await fetch('/api/documents/items?status=processed&page_size=100');
      if (response.ok) {
        const data: DocumentsResponse = await response.json();
        // Filter out already linked documents
        const available = data.items.filter(
          (doc) => !linkedDocumentIds.includes(doc.id)
        );
        setAvailableDocuments(available);
      }
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    } finally {
      setLoadingDocs(false);
    }
  }, [linkedDocumentIds]);

  useEffect(() => {
    if (showAddDialog) {
      fetchAvailableDocuments();
    }
  }, [showAddDialog, fetchAvailableDocuments]);

  const handleUnlinkDocument = async (documentId: string) => {
    setUnlinking(documentId);
    try {
      await achApi.unlinkDocument(matrixId, documentId);
      toast.success('Document unlinked');
      onDocumentsChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to unlink document');
    } finally {
      setUnlinking(null);
    }
  };

  const handleLinkDocuments = async () => {
    if (selectedDocs.length === 0) {
      toast.warning('Please select documents to link');
      return;
    }

    setLinking(true);
    try {
      await achApi.linkDocuments(matrixId, selectedDocs);
      toast.success(`Linked ${selectedDocs.length} document(s)`);
      setSelectedDocs([]);
      setShowAddDialog(false);
      onDocumentsChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to link documents');
    } finally {
      setLinking(false);
    }
  };

  const toggleDocSelection = (docId: string) => {
    setSelectedDocs((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="linked-documents-section">
      <div className="section-header">
        <h3>
          <Icon name="Files" size={18} />
          Linked Documents
        </h3>
        <button className="btn btn-secondary btn-sm" onClick={() => setShowAddDialog(true)}>
          <Icon name="Plus" size={14} />
          Add Documents
        </button>
      </div>

      <p className="section-description">
        Link documents to focus corpus search on specific sources. When linked documents
        exist, corpus search will only search within these documents.
      </p>

      {linkedDocumentIds.length === 0 ? (
        <div className="empty-state">
          <Icon name="FileQuestion" size={32} />
          <p>No documents linked</p>
          <span>Link documents to narrow corpus search scope</span>
        </div>
      ) : (
        <div className="linked-documents-list">
          {linkedDocumentIds.map((docId) => (
            <div key={docId} className="linked-document-item">
              <div className="document-info">
                <Icon name="File" size={16} />
                <span className="document-id" title={docId}>
                  {docId.substring(0, 8)}...
                </span>
              </div>
              <button
                className="btn btn-icon btn-danger-ghost"
                onClick={() => handleUnlinkDocument(docId)}
                disabled={unlinking === docId}
                title="Unlink document"
              >
                {unlinking === docId ? (
                  <Icon name="Loader" size={14} className="spin" />
                ) : (
                  <Icon name="X" size={14} />
                )}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add Documents Dialog */}
      {showAddDialog && (
        <div className="dialog-overlay" onClick={() => setShowAddDialog(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <div className="dialog-header">
              <h2>
                <Icon name="FilePlus" size={20} />
                Link Documents
              </h2>
              <button
                className="btn btn-icon"
                onClick={() => setShowAddDialog(false)}
              >
                <Icon name="X" size={18} />
              </button>
            </div>

            <div className="dialog-content">
              {loadingDocs ? (
                <div className="loading-state">
                  <Icon name="Loader" size={24} className="spin" />
                  <span>Loading documents...</span>
                </div>
              ) : availableDocuments.length === 0 ? (
                <div className="empty-state">
                  <Icon name="FileCheck" size={32} />
                  <p>No available documents</p>
                  <span>All documents are already linked, or no documents exist</span>
                </div>
              ) : (
                <div className="documents-grid">
                  {availableDocuments.map((doc) => (
                    <div
                      key={doc.id}
                      className={`document-card ${selectedDocs.includes(doc.id) ? 'selected' : ''}`}
                      onClick={() => toggleDocSelection(doc.id)}
                    >
                      <div className="document-checkbox">
                        {selectedDocs.includes(doc.id) ? (
                          <Icon name="CheckSquare" size={18} />
                        ) : (
                          <Icon name="Square" size={18} />
                        )}
                      </div>
                      <div className="document-details">
                        <div className="document-name" title={doc.filename}>
                          {doc.filename}
                        </div>
                        <div className="document-meta">
                          <span>{doc.file_type}</span>
                          <span>{formatFileSize(doc.file_size)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="dialog-footer">
              <span className="selection-count">
                {selectedDocs.length} document(s) selected
              </span>
              <div className="dialog-actions">
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowAddDialog(false)}
                >
                  Cancel
                </button>
                <button
                  className="btn btn-primary"
                  onClick={handleLinkDocuments}
                  disabled={selectedDocs.length === 0 || linking}
                >
                  {linking ? (
                    <>
                      <Icon name="Loader" size={14} className="spin" />
                      Linking...
                    </>
                  ) : (
                    <>
                      <Icon name="Link" size={14} />
                      Link Selected
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .linked-documents-section {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          padding: 1.25rem;
          margin-top: 1.5rem;
        }

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 0.75rem;
        }

        .section-header h3 {
          margin: 0;
          font-size: 1rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .section-description {
          font-size: 0.8125rem;
          color: #9ca3af;
          margin: 0 0 1rem 0;
          line-height: 1.5;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2rem;
          color: #6b7280;
          text-align: center;
        }

        .empty-state p {
          margin: 0.5rem 0 0.25rem;
          color: #9ca3af;
        }

        .empty-state span {
          font-size: 0.75rem;
        }

        .linked-documents-list {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
        }

        .linked-document-item {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.375rem 0.5rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
        }

        .document-info {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          color: #d1d5db;
        }

        .document-id {
          font-family: monospace;
          font-size: 0.75rem;
        }

        .btn-danger-ghost {
          padding: 0.25rem;
          color: #9ca3af;
          background: transparent;
          border: none;
          cursor: pointer;
          border-radius: 0.25rem;
        }

        .btn-danger-ghost:hover:not(:disabled) {
          color: #ef4444;
          background: rgba(239, 68, 68, 0.1);
        }

        .btn-danger-ghost:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* Dialog Styles */
        .dialog-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .dialog {
          background: #1f2937;
          border: 1px solid #374151;
          border-radius: 0.5rem;
          width: 90%;
          max-width: 600px;
          max-height: 80vh;
          display: flex;
          flex-direction: column;
        }

        .dialog-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem 1.25rem;
          border-bottom: 1px solid #374151;
        }

        .dialog-header h2 {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          color: #f9fafb;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .dialog-content {
          flex: 1;
          overflow-y: auto;
          padding: 1.25rem;
        }

        .loading-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.75rem;
          padding: 2rem;
          color: #9ca3af;
        }

        .documents-grid {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .document-card {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.75rem;
          background: #111827;
          border: 1px solid #374151;
          border-radius: 0.375rem;
          cursor: pointer;
          transition: all 0.15s;
        }

        .document-card:hover {
          border-color: #4b5563;
        }

        .document-card.selected {
          border-color: #6366f1;
          background: rgba(99, 102, 241, 0.1);
        }

        .document-checkbox {
          color: #6b7280;
        }

        .document-card.selected .document-checkbox {
          color: #6366f1;
        }

        .document-details {
          flex: 1;
          min-width: 0;
        }

        .document-name {
          font-size: 0.875rem;
          color: #f9fafb;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .document-meta {
          display: flex;
          gap: 0.75rem;
          font-size: 0.75rem;
          color: #6b7280;
          margin-top: 0.25rem;
        }

        .dialog-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1rem 1.25rem;
          border-top: 1px solid #374151;
        }

        .selection-count {
          font-size: 0.8125rem;
          color: #9ca3af;
        }

        .dialog-actions {
          display: flex;
          gap: 0.75rem;
        }

        .btn {
          display: inline-flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.5rem 1rem;
          font-size: 0.875rem;
          font-weight: 500;
          border-radius: 0.375rem;
          cursor: pointer;
          transition: all 0.15s;
          border: 1px solid transparent;
        }

        .btn-primary {
          background: #6366f1;
          color: white;
          border-color: #6366f1;
        }

        .btn-primary:hover:not(:disabled) {
          background: #4f46e5;
        }

        .btn-primary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-secondary {
          background: #374151;
          color: #f9fafb;
          border-color: #4b5563;
        }

        .btn-secondary:hover {
          background: #4b5563;
        }

        .btn-sm {
          padding: 0.375rem 0.75rem;
          font-size: 0.8125rem;
        }

        .btn-icon {
          padding: 0.375rem;
          background: transparent;
          border: none;
          color: #9ca3af;
          cursor: pointer;
        }

        .btn-icon:hover {
          color: #f9fafb;
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

import { useState } from 'react';
import { useACHStore } from '../store/useACHStore';
import { Plus, FileText, Trash2, Upload, Scale, Settings, Heart, ExternalLink } from 'lucide-react';
import { Button } from './ui/Button';
import { Dialog } from './ui/Dialog';
import { Input } from './ui/Input';
import { TextArea } from './ui/TextArea';
import { LLMSettings } from './LLMSettings';

export function AnalysisList() {
  const analyses = useACHStore((state) => state.analyses);
  const createAnalysis = useACHStore((state) => state.createAnalysis);
  const loadAnalysis = useACHStore((state) => state.loadAnalysis);
  const deleteAnalysis = useACHStore((state) => state.deleteAnalysis);
  const importFromJSON = useACHStore((state) => state.importFromJSON);

  const [showNewDialog, setShowNewDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<string | null>(null);
  const [showLLMSettings, setShowLLMSettings] = useState(false);

  const [title, setTitle] = useState('');
  const [focusQuestion, setFocusQuestion] = useState('');
  const [description, setDescription] = useState('');
  const [importJson, setImportJson] = useState('');
  const [importError, setImportError] = useState('');

  const handleCreate = () => {
    if (title.trim() && focusQuestion.trim()) {
      createAnalysis(title.trim(), focusQuestion.trim(), description.trim() || undefined);
      setShowNewDialog(false);
      setTitle('');
      setFocusQuestion('');
      setDescription('');
    }
  };

  const handleImport = () => {
    setImportError('');
    if (importFromJSON(importJson)) {
      setShowImportDialog(false);
      setImportJson('');
    } else {
      setImportError('Invalid JSON format. Please check the file and try again.');
    }
  };

  const handleDelete = (id: string) => {
    deleteAnalysis(id);
    setShowDeleteConfirm(null);
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <Scale className="w-10 h-10 text-blue-400" />
          <div>
            <h1 className="text-3xl font-bold text-white">Analysis of Competing Hypotheses</h1>
            <p className="text-gray-400">
              Structured methodology for evaluating competing explanations
              <span className="text-gray-500 mx-2">|</span>
              <a
                href="https://github.com/mantisfury/ArkhamMirror"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300 transition-colors"
              >
                Part of ArkhamMirror
              </a>
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowLLMSettings(true)}
          className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
          title="LLM Settings"
        >
          <Settings className="w-6 h-6" />
        </button>
      </div>

      {/* Actions */}
      <div className="flex gap-3 mb-6">
        <Button onClick={() => setShowNewDialog(true)} icon={<Plus className="w-4 h-4" />}>
          New Analysis
        </Button>
        <Button onClick={() => setShowImportDialog(true)} variant="secondary" icon={<Upload className="w-4 h-4" />}>
          Import
        </Button>
      </div>

      {/* Analysis List */}
      {analyses.length === 0 ? (
        <div className="text-center py-16 bg-gray-800 rounded-lg border border-gray-700">
          <FileText className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <h2 className="text-xl text-gray-300 mb-2">No analyses yet</h2>
          <p className="text-gray-500 mb-6">Create your first ACH analysis to get started</p>
          <Button onClick={() => setShowNewDialog(true)} icon={<Plus className="w-4 h-4" />}>
            Create Analysis
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {analyses.map((analysis) => (
            <div
              key={analysis.id}
              className="bg-gray-800 rounded-lg border border-gray-700 p-4 hover:border-blue-500 transition-colors cursor-pointer card-hover"
              onClick={() => loadAnalysis(analysis.id)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-lg font-semibold text-white truncate">{analysis.title}</h3>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      analysis.status === 'complete' ? 'bg-green-900 text-green-300' :
                      analysis.status === 'in_progress' ? 'bg-blue-900 text-blue-300' :
                      analysis.status === 'archived' ? 'bg-gray-700 text-gray-400' :
                      'bg-yellow-900 text-yellow-300'
                    }`}>
                      {analysis.status.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-gray-400 text-sm line-clamp-2 mb-2">{analysis.focusQuestion}</p>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>{analysis.hypotheses.length} hypotheses</span>
                    <span>{analysis.evidence.length} evidence</span>
                    <span>Step {analysis.currentStep}/8</span>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowDeleteConfirm(analysis.id);
                  }}
                  className="p-2 text-gray-500 hover:text-red-400 hover:bg-gray-700 rounded transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* New Analysis Dialog */}
      <Dialog
        open={showNewDialog}
        onClose={() => setShowNewDialog(false)}
        title="New Analysis"
      >
        <div className="space-y-4">
          <Input
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g., Investigation into Company X"
          />
          <TextArea
            label="Focus Question"
            value={focusQuestion}
            onChange={(e) => setFocusQuestion(e.target.value)}
            placeholder="What specific question are you trying to answer?"
            rows={3}
          />
          <TextArea
            label="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Additional context or notes..."
            rows={2}
          />
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" onClick={() => setShowNewDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={!title.trim() || !focusQuestion.trim()}>
              Create
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Import Dialog */}
      <Dialog
        open={showImportDialog}
        onClose={() => setShowImportDialog(false)}
        title="Import Analysis"
      >
        <div className="space-y-4">
          <TextArea
            label="Paste JSON"
            value={importJson}
            onChange={(e) => setImportJson(e.target.value)}
            placeholder="Paste exported analysis JSON here..."
            rows={10}
          />
          {importError && (
            <p className="text-red-400 text-sm">{importError}</p>
          )}
          <div className="flex justify-end gap-3 mt-6">
            <Button variant="secondary" onClick={() => setShowImportDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleImport} disabled={!importJson.trim()}>
              Import
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={showDeleteConfirm !== null}
        onClose={() => setShowDeleteConfirm(null)}
        title="Delete Analysis"
      >
        <p className="text-gray-300 mb-6">
          Are you sure you want to delete this analysis? This action cannot be undone.
        </p>
        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setShowDeleteConfirm(null)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => showDeleteConfirm && handleDelete(showDeleteConfirm)}
          >
            Delete
          </Button>
        </div>
      </Dialog>

      {/* LLM Settings Dialog */}
      <LLMSettings open={showLLMSettings} onClose={() => setShowLLMSettings(false)} />

      {/* Footer */}
      <footer className="mt-12 pt-6 border-t border-gray-800 text-center">
        <div className="flex items-center justify-center gap-4 text-sm text-gray-500">
          <a
            href="https://github.com/mantisfury/ArkhamMirror"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-300 transition-colors flex items-center gap-1"
          >
            <ExternalLink className="w-3 h-3" />
            ArkhamMirror
          </a>
          <span>|</span>
          <a
            href="https://ko-fi.com/arkhammirror"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-pink-400 transition-colors flex items-center gap-1"
          >
            <Heart className="w-3 h-3" />
            Support on Ko-fi
          </a>
        </div>
        <p className="text-xs text-gray-600 mt-2">
          Based on Richard Heuer's ACH methodology
        </p>
      </footer>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { X, Save, FileText } from 'lucide-react';

const ArticleNotesModal = ({ isOpen, onClose, paper, notes: initialNotes, onSave }) => {
  const [notes, setNotes] = useState(initialNotes || '');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setNotes(initialNotes || '');
    }
  }, [isOpen, initialNotes]);

  if (!isOpen) return null;

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave(notes);
      onClose();
    } catch (error) {
      console.error('Error saving notes:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleClose = () => {
    if (!isSaving) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={handleClose}
    >
      <div
        className="bg-surface rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-faint">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-muted" />
            <h2 className="text-lg font-semibold text-black">Notes</h2>
            {paper && (
              <span className="text-sm text-muted truncate max-w-md">
                {paper.title}
              </span>
            )}
          </div>
          <button
            onClick={handleClose}
            disabled={isSaving}
            className="p-1.5 hover:bg-fill rounded transition-colors disabled:opacity-50"
          >
            <X className="w-5 h-5 text-muted" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add your notes about this article..."
            className="w-full h-64 p-3 border border-faint rounded-lg focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent resize-none text-sm"
            disabled={isSaving}
            autoFocus
          />
          <p className="text-xs text-muted mt-2">
            {notes.length} characters
          </p>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 p-4 border-t border-faint">
          <button
            onClick={handleClose}
            disabled={isSaving}
            className="px-4 py-2 text-sm border border-faint rounded hover:bg-fill transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 text-sm bg-black text-white rounded hover:bg-gray-800 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <Save className="w-4 h-4" />
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ArticleNotesModal;


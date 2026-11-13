import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';
import { useAuth } from '../hooks/useAuth';
import { Folder, Pencil, Trash2, X, Check, Search, AlertCircle } from 'lucide-react';

export default function SavedSearches() {
  const navigate = useNavigate();
  const { user, isAuthenticated, loading: authLoading } = useAuth();
  
  const [searches, setSearches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const [deleteConfirmId, setDeleteConfirmId] = useState(null);

  // Fetch saved searches from Supabase
  const fetchSavedSearches = async () => {
    if (!user) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const { data, error } = await supabase
        .from('saved_searches')
        .select('*')
        .eq('user_id', user.id)
        .order('updated_at', { ascending: false });

      if (error) throw error;
      
      setSearches(data || []);
    } catch (err) {
      console.error('Error fetching saved searches:', err);
      setError('Failed to load saved searches. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      navigate('/auth?mode=login');
      return;
    }
    
    if (user) {
      fetchSavedSearches();
    }
  }, [user, authLoading, isAuthenticated]);

  // Rename a search
  const handleRename = async (id) => {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }

    try {
      const { error } = await supabase
        .from('saved_searches')
        .update({ 
          name: editName.trim(),
          updated_at: new Date().toISOString()
        })
        .eq('id', id)
        .eq('user_id', user.id);

      if (error) throw error;

      setSearches(searches.map(s => 
        s.id === id 
          ? { ...s, name: editName.trim(), updated_at: new Date().toISOString() } 
          : s
      ));
      setEditingId(null);
      setEditName('');
    } catch (err) {
      console.error('Error renaming search:', err);
      setError('Failed to rename search. Please try again.');
    }
  };

  // Delete a search
  const handleDelete = async (id) => {
    try {
      const { error } = await supabase
        .from('saved_searches')
        .delete()
        .eq('id', id)
        .eq('user_id', user.id);

      if (error) throw error;

      setSearches(searches.filter(s => s.id !== id));
      setDeleteConfirmId(null);
    } catch (err) {
      console.error('Error deleting search:', err);
      setError('Failed to delete search. Please try again.');
    }
  };

  // Format date for display
  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    });
  };

  // Navigate to search results
  const handleSearchClick = (search) => {
    if (editingId || deleteConfirmId) return;
    navigate(`/results?topic=${encodeURIComponent(search.query)}`);
  };

  // Start editing
  const startEditing = (search, e) => {
    e.stopPropagation();
    setEditingId(search.id);
    setEditName(search.name);
    setDeleteConfirmId(null);
  };

  // Cancel editing
  const cancelEditing = (e) => {
    e.stopPropagation();
    setEditingId(null);
    setEditName('');
  };

  // Confirm rename
  const confirmRename = (id, e) => {
    e.stopPropagation();
    handleRename(id);
  };

  // Show delete confirmation
  const showDeleteConfirm = (id, e) => {
    e.stopPropagation();
    setDeleteConfirmId(id);
    setEditingId(null);
  };

  // Cancel delete
  const cancelDelete = (e) => {
    e.stopPropagation();
    setDeleteConfirmId(null);
  };

  // Confirm delete
  const confirmDelete = (id, e) => {
    e.stopPropagation();
    handleDelete(id);
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-black mb-4"></div>
          <p className="text-gray-600">Loading saved searches...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-black">Saved Searches</h1>
          <p className="text-gray-500 mt-1">Manage your saved research queries</p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <p className="text-red-700 text-sm">{error}</p>
            <button 
              onClick={() => setError(null)}
              className="ml-auto text-red-500 hover:text-red-700"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Searches Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-6 py-3 bg-gray-50 border-b border-gray-200">
            <div className="col-span-6 text-sm font-medium text-gray-600">Name</div>
            <div className="col-span-4 text-sm font-medium text-gray-600">Last updated</div>
            <div className="col-span-2 text-sm font-medium text-gray-600 text-right">Actions</div>
          </div>

          {/* Table Body */}
          {searches.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500 text-lg">No saved searches</p>
            </div>
          ) : (
            <div>
              {searches.map((search) => (
                <div
                  key={search.id}
                  onClick={() => handleSearchClick(search)}
                  className={`grid grid-cols-12 gap-4 px-6 py-4 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 transition-colors ${
                    editingId !== search.id && deleteConfirmId !== search.id ? 'cursor-pointer' : ''
                  }`}
                >
                  {/* Name Column */}
                  <div className="col-span-6 flex items-center gap-3">
                    <Folder className="w-5 h-5 text-gray-400 flex-shrink-0" />
                    {editingId === search.id ? (
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') confirmRename(search.id, e);
                          if (e.key === 'Escape') cancelEditing(e);
                        }}
                        className="flex-1 px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-black focus:border-transparent text-sm"
                        autoFocus
                      />
                    ) : (
                      <span className="text-black font-medium truncate">{search.name}</span>
                    )}
                  </div>

                  {/* Last Updated Column */}
                  <div className="col-span-4 flex items-center">
                    <span className="text-gray-500 text-sm">{formatDate(search.updated_at)}</span>
                  </div>

                  {/* Actions Column */}
                  <div className="col-span-2 flex items-center justify-end gap-2">
                    {deleteConfirmId === search.id ? (
                      <>
                        <button
                          onClick={(e) => confirmDelete(search.id, e)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Confirm delete"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={cancelDelete}
                          className="p-1.5 text-gray-500 hover:bg-gray-100 rounded transition-colors"
                          title="Cancel"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : editingId === search.id ? (
                      <>
                        <button
                          onClick={(e) => confirmRename(search.id, e)}
                          className="p-1.5 text-green-600 hover:bg-green-50 rounded transition-colors"
                          title="Save"
                        >
                          <Check className="w-4 h-4" />
                        </button>
                        <button
                          onClick={cancelEditing}
                          className="p-1.5 text-gray-500 hover:bg-gray-100 rounded transition-colors"
                          title="Cancel"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={(e) => startEditing(search, e)}
                          className="p-1.5 text-gray-400 hover:text-black hover:bg-gray-100 rounded transition-colors"
                          title="Rename"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => showDeleteConfirm(search.id, e)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        {searches.length > 0 && (
          <p className="text-center text-gray-400 text-sm mt-6">
            Click on a search to view results
          </p>
        )}
      </div>
    </div>
  );
}


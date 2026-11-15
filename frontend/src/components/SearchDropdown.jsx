import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  ChevronDown, Trash2, FolderOpen, Save, Pencil, ChevronRight 
} from 'lucide-react';
import { supabase } from '../lib/supabase';
import { useAuth } from '../hooks/useAuth';

export default function SearchDropdown({ topic, searchQuery }) {
  const navigate = useNavigate();
  const { user, isAuthenticated } = useAuth();
  
  const [searchMenuOpen, setSearchMenuOpen] = useState(false);
  const [savedSearchName, setSavedSearchName] = useState('Unsaved search');
  const [currentSearchId, setCurrentSearchId] = useState(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [modalInputValue, setModalInputValue] = useState('');
  const [savedSearches, setSavedSearches] = useState([]);
  const [openSubmenuOpen, setOpenSubmenuOpen] = useState(false);
  const [modalError, setModalError] = useState('');
  const searchMenuRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchMenuRef.current && !searchMenuRef.current.contains(event.target)) {
        setSearchMenuOpen(false);
        setOpenSubmenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch saved searches for "Open" submenu
  const fetchSavedSearches = async () => {
    if (!user) return;
    try {
      const { data, error } = await supabase
        .from('saved_searches')
        .select('*')
        .eq('user_id', user.id)
        .order('updated_at', { ascending: false });
      if (!error) setSavedSearches(data || []);
    } catch (err) {
      console.error('Error fetching saved searches:', err);
    }
  };

  // Save current search
  const handleSaveAs = async () => {
    if (!user || !modalInputValue.trim()) return;
    setModalError('');
    
    try {
      // Check if name already exists for this user
      const { data: existingSearch } = await supabase
        .from('saved_searches')
        .select('id')
        .eq('user_id', user.id)
        .eq('name', modalInputValue.trim())
        .single();
      
      if (existingSearch) {
        setModalError('A search with this name already exists');
        return;
      }

      const { data, error } = await supabase
        .from('saved_searches')
        .insert({
          user_id: user.id,
          name: modalInputValue.trim(),
          query: topic || searchQuery,
          updated_at: new Date().toISOString()
        })
        .select()
        .single();
      
      if (!error && data) {
        setSavedSearchName(data.name);
        setCurrentSearchId(data.id);
        setShowSaveModal(false);
        setModalInputValue('');
        setModalError('');
      }
    } catch (err) {
      console.error('Error saving search:', err);
    }
  };

  // Rename current search
  const handleRename = async () => {
    if (!user || !currentSearchId || !modalInputValue.trim()) return;
    setModalError('');
    
    try {
      // Check if name already exists for this user (excluding current search)
      const { data: existingSearch } = await supabase
        .from('saved_searches')
        .select('id')
        .eq('user_id', user.id)
        .eq('name', modalInputValue.trim())
        .neq('id', currentSearchId)
        .single();
      
      if (existingSearch) {
        setModalError('A search with this name already exists');
        return;
      }

      const { error } = await supabase
        .from('saved_searches')
        .update({ 
          name: modalInputValue.trim(),
          updated_at: new Date().toISOString()
        })
        .eq('id', currentSearchId)
        .eq('user_id', user.id);
      
      if (!error) {
        setSavedSearchName(modalInputValue.trim());
        setShowRenameModal(false);
        setModalInputValue('');
        setModalError('');
      }
    } catch (err) {
      console.error('Error renaming search:', err);
    }
  };

  // Delete current search
  const handleDeleteSearch = async () => {
    if (!user || !currentSearchId) return;
    try {
      const { error } = await supabase
        .from('saved_searches')
        .delete()
        .eq('id', currentSearchId)
        .eq('user_id', user.id);
      
      if (!error) {
        setSavedSearchName('Unsaved search');
        setCurrentSearchId(null);
        setSearchMenuOpen(false);
      }
    } catch (err) {
      console.error('Error deleting search:', err);
    }
  };

  // Open a saved search
  const handleOpenSearch = (search) => {
    setSavedSearchName(search.name);
    setCurrentSearchId(search.id);
    setSearchMenuOpen(false);
    setOpenSubmenuOpen(false);
    navigate(`/results?topic=${encodeURIComponent(search.query)}`);
  };

  // View all saved searches
  const handleViewAll = () => {
    setSearchMenuOpen(false);
    setOpenSubmenuOpen(false);
    navigate('/saved-searches');
  };

  // Get first 3 saved searches for the submenu
  const recentSearches = savedSearches.slice(0, 3);

  return (
    <>
      {/* Save/Rename Modal */}
      {(showSaveModal || showRenameModal) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-surface rounded-xl p-6 w-full max-w-md shadow-2xl">
            <h3 className="text-lg font-semibold text-ink mb-4">
              {showSaveModal ? 'Save Search' : 'Rename Search'}
            </h3>
            <input
              type="text"
              value={modalInputValue}
              onChange={(e) => {
                setModalInputValue(e.target.value);
                setModalError(''); // Clear error when user types
              }}
              placeholder="Enter search name..."
              className={`w-full px-4 py-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-black text-base ${
                modalError ? 'border-danger' : 'border-faint'
              }`}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') showSaveModal ? handleSaveAs() : handleRename();
                if (e.key === 'Escape') { setShowSaveModal(false); setShowRenameModal(false); setModalError(''); }
              }}
            />
            {modalError && (
              <p className="mt-2 text-sm text-danger">{modalError}</p>
            )}
            <div className="flex justify-end gap-3 mt-5">
              <button
                onClick={() => { setShowSaveModal(false); setShowRenameModal(false); setModalInputValue(''); setModalError(''); }}
                className="px-5 py-2.5 text-muted hover:text-black font-medium transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={showSaveModal ? handleSaveAs : handleRename}
                disabled={!modalInputValue.trim()}
                className="px-5 py-2.5 bg-gray-700 text-white rounded-lg hover:bg-gray-600 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium transition-colors"
              >
                {showSaveModal ? 'Save' : 'Rename'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Search Dropdown */}
      <div className="relative" ref={searchMenuRef}>
        <button
          onClick={() => {
            setSearchMenuOpen(!searchMenuOpen);
            if (!searchMenuOpen && isAuthenticated) fetchSavedSearches();
          }}
          className="flex items-center gap-1.5 border border-faint rounded-md pl-3 pr-2 py-1 hover:bg-fill transition-colors"
        >
          <span className="text-ink-soft text-sm">{savedSearchName}</span>
          <ChevronDown className="w-3.5 h-3.5 text-muted" />
        </button>

        {searchMenuOpen && (
          <div className="absolute top-full left-0 mt-1 w-56 bg-surface rounded-lg shadow-xl border border-faint py-1.5 z-50">
            {/* Open with submenu */}
            <div
              className="relative group"
              onMouseEnter={() => setOpenSubmenuOpen(true)}
              onMouseLeave={() => setOpenSubmenuOpen(false)}
            >
              <button className="w-full px-3 py-2 text-left text-ink-soft font-medium hover:bg-fill flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <FolderOpen className="w-4 h-4" />
                  Open
                </span>
                <ChevronRight className="w-4 h-4" />
              </button>
              
              {openSubmenuOpen && (
                <div className="absolute left-full top-0 -ml-1 pl-2">
                  <div className="w-56 bg-surface rounded-lg shadow-xl border border-faint py-1.5">
                    {!isAuthenticated ? (
                      <p className="px-3 py-2 text-muted">Login to view saved searches</p>
                    ) : recentSearches.length === 0 ? (
                      <p className="px-3 py-2 text-muted">No saved searches</p>
                    ) : (
                      <>
                        {recentSearches.map(search => (
                          <button
                            key={search.id}
                            onClick={() => handleOpenSearch(search)}
                            className="w-full px-3 py-2 text-left text-ink-soft hover:bg-fill truncate"
                          >
                            {search.name}
                          </button>
                        ))}
                        {savedSearches.length > 0 && (
                          <>
                            <hr className="my-1.5 border-faint" />
                            <button
                              onClick={handleViewAll}
                              className="w-full px-3 py-2 text-left text-muted font-medium hover:bg-fill"
                            >
                              View all →
                            </button>
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            <hr className="my-1.5 border-faint" />

            {/* Save As */}
            <button
              onClick={() => {
                if (!isAuthenticated) {
                  navigate('/auth?mode=login');
                  return;
                }
                setModalInputValue(topic || searchQuery || '');
                setShowSaveModal(true);
                setSearchMenuOpen(false);
              }}
              className="w-full px-3 py-2 text-left text-ink-soft hover:bg-fill flex items-center gap-2"
            >
              <Save className="w-4 h-4" />
              Save As...
            </button>

            {/* Rename */}
            <button
              onClick={() => {
                if (currentSearchId) {
                  setModalInputValue(savedSearchName);
                  setShowRenameModal(true);
                  setSearchMenuOpen(false);
                }
              }}
              disabled={!currentSearchId}
              className="w-full px-3 py-2 text-left text-ink-soft font-medium hover:bg-fill flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Pencil className="w-4 h-4" />
              Rename
            </button>

            {/* Delete */}
            <button
              onClick={handleDeleteSearch}
              disabled={!currentSearchId}
              className="w-full px-3 py-2 text-left text-danger font-medium hover:bg-danger-soft flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          </div>
        )}
      </div>
    </>
  );
}

import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { searchAPI, savedArticlesAPI, arxivAPI, coreAPI, pmcAPI, semanticScholarAPI, crossrefAPI, europePmcAPI, pubmedAPI, doajAPI, unpaywallAPI, draftAPI, chatAPI, checkAiReady, APIError } from '../services/api';
import {
  BookOpen, X, FileText, MessageSquare, Code, Download,
  ChevronDown, ChevronUp, Plus, Trash2, MoreVertical, ArrowUpDown, BarChart3, CheckSquare, Network,
  Check, Bookmark, Share2, Copy, CheckCircle, Building2, Send, Bot, User, Compass, TrendingUp,
  PenLine, Image, ClipboardCopy, Eye, EyeOff, Filter
} from 'lucide-react';
import SearchDropdown from '../components/SearchDropdown';
import CitationMesh from '../components/CitationMesh';
import ArticleNotesModal from '../components/ArticleNotesModal';
import FloatingBubbles from '../components/FloatingBubbles';

import { ToastContainer } from '../components/Toast';
import { useToast } from '../hooks/useToast';
import { useAuth } from '../hooks/useAuth';
import { supabase } from '../lib/supabase';
import * as XLSX from 'xlsx';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import { useSearchHistory } from '../hooks/useSearchHistory';
import SearchBar from '../components/SearchBar';

// Compact paper card for the list (left column) - arXiv style
const PaperListItem = ({ paper, isSelected, onClick }) => {
  // Support both arXiv and OpenAlex paper formats
  const authors = Array.isArray(paper.authors) && paper.authors.length > 0
    ? paper.authors.slice(0, 2).map(a => typeof a === 'string' ? a : a.name || a).join(', ') + (paper.authors.length > 2 ? ', et al.' : '')
    : 'Unknown Authors';

  // Use allSources for multi-source display, fallback to single source detection
  const allSources = paper.allSources || [paper.source || 'Unknown'];
  const isArxiv = allSources.includes('arXiv') || paper.arxiv_id;
  const isCore = allSources.includes('CORE') || paper.core_id;
  const isPmc = allSources.includes('PMC') || paper.pmc_id;
  const isOpenAlex = allSources.includes('OpenAlex');
  const isCrossref = allSources.includes('Crossref') || paper.crossref_id;
  const isEuropePmc = allSources.includes('Europe PMC') || paper.europe_pmc_id || paper.pmcid;
  const isPubmed = allSources.includes('PubMed') || paper.pubmed_id || paper.pmid;
  const isDoaj = allSources.includes('DOAJ') || paper.doaj_id;
  const isUnpaywall = allSources.includes('Unpaywall') || paper.unpaywall_id;
  const isSemanticScholar = allSources.includes('Semantic Scholar') || (paper.semantic_scholar_id && !isArxiv && !isCore && !isPmc && !isOpenAlex && !isCrossref && !isEuropePmc && !isPubmed && !isDoaj && !isUnpaywall);
  const arxivId = paper.arxiv_id;
  const pmcId = paper.pmc_id;
  const publishedDate = paper.published_date ? new Date(paper.published_date).getFullYear() : null;
  const year = paper.year || publishedDate;
  const venue = paper.venue && paper.venue !== 'N/A' ? paper.venue : null;
  const citationCount = paper.citationCount || 0;
  const pdfUrl = paper.pdf_url || paper.openAccessPdf || (paper.url && paper.url.toLowerCase().endsWith('.pdf') ? paper.url : null);
  const abstract = paper.abstract || '';
  const abstractPreview = abstract.length > 200 ? abstract.substring(0, 200) + '...' : abstract;

  return (
    <div className={`border-b border-gray-200 ${isSelected ? 'bg-gray-100' : 'bg-white'}`}>
      <div
        onClick={onClick}
        className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors`}
      >
        <h3 className="text-base font-semibold text-black mb-1.5 line-clamp-2 hover:text-gray-700 transition-colors">
          {paper.title || 'Untitled Paper'}
        </h3>

        <div className="text-sm text-gray-600 mb-2">
          {isOpenAlex && <span className="font-mono text-xs bg-amber-100 px-1.5 py-0.5 rounded text-amber-800 mr-1">OpenAlex</span>}
          {isArxiv && <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded mr-1">{arxivId ? `arXiv:${arxivId}` : 'arXiv'}</span>}
          {isCore && <span className="font-mono text-xs bg-blue-100 px-1.5 py-0.5 rounded text-blue-800 mr-1">CORE</span>}
          {isPmc && <span className="font-mono text-xs bg-green-100 px-1.5 py-0.5 rounded text-green-800 mr-1">{pmcId ? `PMC:${pmcId}` : 'PMC'}</span>}
          {isSemanticScholar && <span className="font-mono text-xs bg-purple-100 px-1.5 py-0.5 rounded text-purple-800 mr-1">Semantic Scholar</span>}
          {isCrossref && <span className="font-mono text-xs bg-teal-100 px-1.5 py-0.5 rounded text-teal-800 mr-1">Crossref</span>}
          {isEuropePmc && <span className="font-mono text-xs bg-pink-100 px-1.5 py-0.5 rounded text-pink-800 mr-1">Europe PMC</span>}
          {isPubmed && <span className="font-mono text-xs bg-cyan-100 px-1.5 py-0.5 rounded text-cyan-800 mr-1">PubMed</span>}
          {isDoaj && <span className="font-mono text-xs bg-orange-100 px-1.5 py-0.5 rounded text-orange-800 mr-1">DOAJ</span>}
          {isUnpaywall && <span className="font-mono text-xs bg-lime-100 px-1.5 py-0.5 rounded text-lime-800 mr-1">Unpaywall</span>}
          {year && <span className="ml-1">{year}</span>}
          {authors && <span className="ml-2">{authors}</span>}
          {venue && <span className="ml-2"> · {venue}</span>}
        </div>

        {abstract && (
          <div className="text-sm text-gray-600 mb-2 line-clamp-2">
            {abstractPreview}
          </div>
        )}

        <div className="flex items-center justify-between text-sm text-gray-500">
          {!isArxiv && <span>Cited by {citationCount.toLocaleString()}</span>}
          {pdfUrl && (
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="text-black hover:text-gray-700 font-medium"
            >
              PDF
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

// Stats Panel Component (Right Column)
const StatsPanel = ({
  papers,
  onClose,
  selectedTypes,
  setSelectedTypes,
  selectedSources,
  setSelectedSources,
  selectedInstitutions,
  setSelectedInstitutions,
  onRelatedSearch,
  relatedSearches,
  relatedLoading,
}) => {
  const [expandedSections, setExpandedSections] = useState({
    relatedSearches: true,
    topic: false,
    institution: true,
    type: true,
    source: true
  });

  // Memoize stats calculations - only recalculate when papers change
  const { sortedInstitutions, sortedTypes, sortedSources } = useMemo(() => {
    // Calculate stats from papers
    const openAccessCount = papers.filter(p => p.isOpenAccess).length;
    const openAccessPercent = papers.length > 0 ? Math.round((openAccessCount / papers.length) * 100) : 0;

    // Group by year
    const yearDistribution = {};
    papers.forEach(p => {
      if (p.year) {
        yearDistribution[p.year] = (yearDistribution[p.year] || 0) + 1;
      }
    });
    const sortedYears = Object.keys(yearDistribution).sort((a, b) => b - a).slice(0, 10);
    const maxYearCount = Math.max(...Object.values(yearDistribution), 1);

    // Group by fields of study
    const topicCounts = {};
    papers.forEach(p => {
      if (Array.isArray(p.fieldsOfStudy)) {
        p.fieldsOfStudy.forEach(field => {
          topicCounts[field] = (topicCounts[field] || 0) + 1;
        });
      }
    });
    const sortedTopics = Object.entries(topicCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    // Group by institutions - optimized for instant loading
    const institutionCounts = {};
    papers.forEach(p => {
      if (Array.isArray(p.institutions)) {
        p.institutions.forEach(inst => {
          if (inst && inst.trim()) {
            institutionCounts[inst] = (institutionCounts[inst] || 0) + 1;
          }
        });
      }
    });
    const sortedInstitutions = Object.entries(institutionCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    // Group by type
    const typeCounts = {};
    papers.forEach(p => {
      const type = p.publicationTypes && p.publicationTypes.length > 0
        ? p.publicationTypes[0]
        : 'article';
      typeCounts[type] = (typeCounts[type] || 0) + 1;
    });
    const sortedTypes = Object.entries(typeCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);

    // Group by source (arXiv, OpenAlex, PMC, CORE, etc.)
    const sourceCounts = {};
    papers.forEach(p => {
      const sources = p.allSources || [p.source || 'Unknown'];
      sources.forEach(src => {
        if (src && src.trim()) {
          sourceCounts[src] = (sourceCounts[src] || 0) + 1;
        }
      });
    });
    const sortedSources = Object.entries(sourceCounts)
      .sort((a, b) => b[1] - a[1]);

    return {
      openAccessCount,
      openAccessPercent,
      sortedYears,
      maxYearCount,
      yearDistribution,
      sortedTopics,
      sortedInstitutions,
      sortedTypes,
      sortedSources
    };
  }, [papers]);

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  return (
    <div className="w-full md:w-80 bg-white border-l border-gray-200 overflow-y-auto">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-center justify-between z-10">
        <h2 className="text-lg font-semibold text-black">Stats</h2>
        <div className="flex items-center gap-2">
          <button className="p-1.5 hover:bg-gray-100 rounded">
            <Plus className="w-4 h-4 text-gray-600" />
          </button>
          <button className="p-1.5 hover:bg-gray-100 rounded">
            <Download className="w-4 h-4 text-gray-600" />
          </button>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded">
            <X className="w-4 h-4 text-gray-600" />
          </button>
        </div>
      </div>

      <div className="p-4 space-y-6 md:space-y-4">

        {/* Related Searches */}
        <div className="border-b border-gray-200 pb-4 pt-2">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Compass className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-black">Related Searches</span>
            </div>
            <button onClick={() => toggleSection('relatedSearches')}>
              <ChevronDown className={`w-4 h-4 text-gray-600 transition-transform ${expandedSections.relatedSearches ? '' : '-rotate-90'}`} />
            </button>
          </div>
          {expandedSections.relatedSearches && (
            <div className="space-y-1">
              {relatedLoading ? (
                <div className="flex items-center gap-2 py-3 text-gray-400 text-xs">
                  <div className="w-3.5 h-3.5 border-2 border-gray-300 border-t-transparent rounded-full animate-spin" />
                  Loading related topics...
                </div>
              ) : relatedSearches.length > 0 ? (
                relatedSearches.map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => onRelatedSearch && onRelatedSearch(item.text)}
                    className="w-full text-left px-2 py-2 rounded-md hover:bg-gray-50 flex items-start gap-2.5 group transition-colors"
                  >
                    <TrendingUp className="w-3.5 h-3.5 text-gray-400 group-hover:text-black mt-0.5 flex-shrink-0 transition-colors" />
                    <div className="flex flex-col overflow-hidden">
                      <span className="text-sm text-gray-700 group-hover:text-black truncate transition-colors">{item.text}</span>
                      {item.hint && (
                        <span className="text-[10px] text-gray-400 truncate">{item.hint}</span>
                      )}
                    </div>
                  </button>
                ))
              ) : (
                <p className="text-xs text-gray-400 py-2">No related topics found</p>
              )}
            </div>
          )}
        </div>

        {/* Institution */}
        <div className="border-b border-gray-200 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-black">Institution</span>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-1 hover:bg-gray-100 rounded">
                <MoreVertical className="w-4 h-4 text-gray-600" />
              </button>
              <button onClick={() => toggleSection('institution')}>
                <X className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
          {expandedSections.institution && (
            <div className="space-y-1">
              {sortedInstitutions.length > 0 ? (
                <>
                  {sortedInstitutions.map(([institution, count]) => (
                    <label key={institution} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded">
                      <input
                        type="checkbox"
                        checked={selectedInstitutions.includes(institution)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedInstitutions([...selectedInstitutions, institution]);
                          } else {
                            setSelectedInstitutions(selectedInstitutions.filter(i => i !== institution));
                          }
                        }}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm text-gray-700 flex-1">{institution}</span>
                      <span className="text-sm text-gray-500">{count.toLocaleString()}</span>
                    </label>
                  ))}
                  {sortedInstitutions.length >= 10 && (
                    <button className="text-xs text-gray-500 hover:text-black mt-2">More...</button>
                  )}
                </>
              ) : (
                <p className="text-sm text-gray-500 py-2">No institution data available</p>
              )}
            </div>
          )}
        </div>

        {/* Type */}
        <div className="border-b border-gray-200 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <CheckSquare className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-black">Type</span>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-1 hover:bg-gray-100 rounded">
                <MoreVertical className="w-4 h-4 text-gray-600" />
              </button>
              <button onClick={() => toggleSection('type')}>
                <X className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
          {expandedSections.type && (
            <div className="space-y-1">
              {sortedTypes.map(([type, count]) => (
                <label key={type} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded">
                  <input
                    type="checkbox"
                    checked={selectedTypes.includes(type)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedTypes([...selectedTypes, type]);
                      } else {
                        setSelectedTypes(selectedTypes.filter(t => t !== type));
                      }
                    }}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm text-gray-700 flex-1 capitalize">{type}</span>
                  <span className="text-sm text-gray-500">{count.toLocaleString()}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Source */}
        <div className="border-b border-gray-200 pb-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-black">Source</span>
            </div>
            <div className="flex items-center gap-2">
              <button className="p-1 hover:bg-gray-100 rounded">
                <MoreVertical className="w-4 h-4 text-gray-600" />
              </button>
              <button onClick={() => toggleSection('source')}>
                <X className="w-4 h-4 text-gray-600" />
              </button>
            </div>
          </div>
          {expandedSections.source && (
            <div className="space-y-1">
              {sortedSources.length > 0 ? (
                <>
                  {sortedSources.map(([source, count]) => (
                    <label key={source} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded">
                      <input
                        type="checkbox"
                        checked={selectedSources.includes(source)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedSources([...selectedSources, source]);
                          } else {
                            setSelectedSources(selectedSources.filter(s => s !== source));
                          }
                        }}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm text-gray-700 flex-1">{source}</span>
                      <span className="text-sm text-gray-500">{count.toLocaleString()}</span>
                    </label>
                  ))}
                </>
              ) : (
                <p className="text-sm text-gray-500 py-2">No source data available</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Detailed slide-in panel (right column)
const DetailPanel = ({ paper, onClose, summaryJobs, onStartSummarize, isSplitScreen, unpaywallPdfUrl }) => {
  // All hooks below run unconditionally, before any early return, so the
  // hook order stays stable even when paper is null. The null-paper
  // early return lives after the last hook.
  const { isAuthenticated } = useAuth();
  const { toasts, showToast, removeToast } = useToast();
  const navigate = useNavigate();

  const authors = Array.isArray(paper?.authors) ? paper.authors : [];
  const venue = paper?.venue && paper.venue !== 'N/A' ? paper.venue : null;
  const year = paper?.year || null;
  const citationCount = paper?.citationCount || 0;
  const referenceCount = paper?.referenceCount || 0;
  const doi = paper?.externalIds && (paper.externalIds.DOI || paper.externalIds.doi);
  const pdfUrl = paper?.pdf_url || paper?.openAccessPdf || (paper?.url && paper.url.toLowerCase().endsWith('.pdf') ? paper.url : null);
  const htmlUrl = paper?.url && !pdfUrl ? paper.url : null;
  const fields = Array.isArray(paper?.fieldsOfStudy) ? paper.fieldsOfStudy : [];
  const isOpenAccess = Boolean(paper?.isOpenAccess);
  const [abstractExpanded, setAbstractExpanded] = useState(false);

  // State for saved articles functionality
  const [isSaved, setIsSaved] = useState(false);
  const [, setSavedArticleId] = useState(null);
  const [notes, setNotes] = useState('');
  const [showNotesModal, setShowNotesModal] = useState(false);
  const [showLinkDropdown, setShowLinkDropdown] = useState(false);
  const [copiedToClipboard, setCopiedToClipboard] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(true);
  const [pdfContent, setPdfContent] = useState(null);
  // Summary state is now derived from the parent's summaryJobs map
  // so it persists even when the panel is closed/reopened
  const [showChat, setShowChat] = useState(false);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatSessionId, setChatSessionId] = useState(null);

  const [draft, setDraft] = useState(null);
  const [draftFigures, setDraftFigures] = useState([]);
  const [draftGenerating, setDraftGenerating] = useState(false);
  const [draftProgress, setDraftProgress] = useState('');
  const [draftCollapsed, setDraftCollapsed] = useState({});
  const [draftMinimized, setDraftMinimized] = useState(false);

  // Refs for auto-scrolling to summary and chat sections
  const summaryRef = useRef(null);
  const chatRef = useRef(null);
  const draftRef = useRef(null);

  const abstract = paper?.abstract && paper.abstract !== 'N/A' ? paper.abstract : null;
  const abstractPreview = abstract && abstract.length > 300 ? abstract.substring(0, 300) + '...' : abstract;

  // Derive summary state from the shared summaryJobs map
  const paperId = paper?.paperId || paper?.id || paper?.arxiv_id || paper?.core_id || paper?.pmc_id || paper?.semantic_scholar_id || paper?.crossref_id || paper?.europe_pmc_id || paper?.pubmed_id || paper?.doaj_id || paper?.unpaywall_id;
  const currentJob = summaryJobs?.get(paperId);
  const summarizing = currentJob?.status === 'loading';
  const summary = currentJob?.status === 'done' ? currentJob.summary : null;

  const paperIdForSaved = paper?.paperId || paper?.id || paper?.arxiv_id || paper?.core_id || paper?.pmc_id || paper?.semantic_scholar_id || paper?.crossref_id || paper?.europe_pmc_id || paper?.pubmed_id || paper?.doaj_id || paper?.unpaywall_id;
  const isArxiv = paper?.source === 'arXiv' || paper?.arxiv_id;
  const isCore = paper?.source === 'CORE' || paper?.core_id;
  const isPmc = paper?.source === 'PMC' || paper?.pmc_id;
  const isOpenAlex = paper?.source === 'OpenAlex';
  const isCrossref = paper?.source === 'Crossref' || paper?.crossref_id;
  const isEuropePmc = paper?.source === 'Europe PMC' || paper?.europe_pmc_id || paper?.pmcid;
  const isPubmed = paper?.source === 'PubMed' || paper?.pubmed_id || paper?.pmid;
  const isDoaj = paper?.source === 'DOAJ' || paper?.doaj_id;
  const isUnpaywall = paper?.source === 'Unpaywall' || paper?.unpaywall_id;
  const isSemanticScholar = paper?.source === 'Semantic Scholar' || (paper?.semantic_scholar_id && !isArxiv && !isCore && !isPmc && !isOpenAlex && !isCrossref && !isEuropePmc && !isPubmed && !isDoaj && !isUnpaywall);
  const pdfUrlForExtract = paper?.pdf_url || paper?.openAccessPdf || pdfUrl || unpaywallPdfUrl;

  // Reset PDF content, chat, and draft when paper changes
  // NOTE: summary/summarizing are NOT reset here — they are derived from
  // the parent's summaryJobs map, so background jobs survive panel changes.
  useEffect(() => {
    if (!paper) return;
    setPdfContent(null);
    setShowChat(false);
    setChatMessages([]);
    setChatInput('');
    setChatSessionId(null);

    setDraft(null);
    setDraftFigures([]);
    setDraftGenerating(false);
    setDraftProgress('');
    setDraftCollapsed({});
    setDraftMinimized(false);

    // If we have a completed summary job, restore the PDF content from it
    const job = summaryJobs?.get(paperId);
    if (job?.status === 'done' && job.fullText) {
      setPdfContent(job.fullText);
    }
  }, [paper]);


  // Auto-scroll to summary when a background job completes while panel is open
  useEffect(() => {
    if (summary && summaryRef.current) {
      setTimeout(() => {
        summaryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 200);
    }
  }, [summary]);

  // Check if article is saved when component mounts or paper changes
  useEffect(() => {
    const checkSavedStatus = async () => {
      if (!isAuthenticated || !paperIdForSaved) {
        setLoadingSaved(false);
        return;
      }

      try {
        const savedArticle = await savedArticlesAPI.getSavedArticle(paperIdForSaved);
        if (savedArticle) {
          setIsSaved(true);
          setSavedArticleId(savedArticle.id);
          setNotes(savedArticle.notes || '');
        } else {
          setIsSaved(false);
          setSavedArticleId(null);
          setNotes('');
        }
      } catch (error) {
        console.error('Error checking saved status:', error);
      } finally {
        setLoadingSaved(false);
      }
    };

    checkSavedStatus();
  }, [paperIdForSaved, isAuthenticated]);

  // Close link dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showLinkDropdown && !event.target.closest('.link-dropdown-container')) {
        setShowLinkDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showLinkDropdown]);

  // Early return only after every hook above has run unconditionally.
  if (!paper) return null;

  // API Button Handler - Copy JSON to clipboard
  const handleCopyJSON = async () => {
    try {
      const jsonData = JSON.stringify(paper, null, 2);
      await navigator.clipboard.writeText(jsonData);
      showToast('Paper data copied to clipboard as JSON', 'success');
    } catch (error) {
      console.error('Error copying to clipboard:', error);
      showToast('Failed to copy to clipboard', 'error');
    }
  };

  // Link Button Handlers
  const handleCopyURL = async () => {
    const urlToCopy = htmlUrl || paper.url || window.location.href;
    try {
      await navigator.clipboard.writeText(urlToCopy);
      setCopiedToClipboard(true);
      showToast('URL copied to clipboard', 'success');
      setTimeout(() => setCopiedToClipboard(false), 2000);
      setShowLinkDropdown(false);
    } catch (error) {
      console.error('Error copying URL:', error);
      showToast('Failed to copy URL', 'error');
    }
  };

  const handleShare = async () => {
    const shareData = {
      title: paper.title || 'Research Paper',
      text: paper.abstract ? paper.abstract.substring(0, 200) : '',
      url: htmlUrl || paper.url || window.location.href,
    };

    try {
      if (navigator.share && navigator.canShare && navigator.canShare(shareData)) {
        await navigator.share(shareData);
        showToast('Article shared successfully', 'success');
      } else {
        // Fallback to copy URL
        await handleCopyURL();
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Error sharing:', error);
        // Fallback to copy URL
        await handleCopyURL();
      }
    }
    setShowLinkDropdown(false);
  };

  // Message/Save Button Handlers
  const handleSaveArticle = async () => {
    if (!isAuthenticated) {
      showToast('Please log in to save articles', 'info');
      navigate('/auth?mode=login');
      return;
    }

    try {
      if (isSaved) {
        await savedArticlesAPI.unsaveArticle(paperIdForSaved);
        setIsSaved(false);
        setSavedArticleId(null);
        setNotes('');
        showToast('Article removed from saved', 'success');
      } else {
        const savedArticle = await savedArticlesAPI.saveArticle(paperIdForSaved, paper);
        setIsSaved(true);
        setSavedArticleId(savedArticle.id);
        showToast('Article saved to favorites', 'success');
      }
    } catch (error) {
      console.error('Error saving article:', error);
      if (error instanceof APIError && error.status === 401) {
        showToast('Please log in to save articles', 'info');
        navigate('/auth?mode=login');
      } else {
        showToast('Failed to save article', 'error');
      }
    }
  };

  const handleOpenNotes = () => {
    if (!isAuthenticated) {
      showToast('Please log in to add notes', 'info');
      navigate('/auth?mode=login');
      return;
    }

    // If not saved, save it first
    if (!isSaved) {
      handleSaveArticle().then(() => {
        setShowNotesModal(true);
      });
    } else {
      setShowNotesModal(true);
    }
  };

  const handleSaveNotes = async (newNotes) => {
    try {
      await savedArticlesAPI.updateArticleNotes(paperIdForSaved, newNotes);
      setNotes(newNotes);
      showToast('Notes saved successfully', 'success');
    } catch (error) {
      console.error('Error saving notes:', error);
      showToast('Failed to save notes', 'error');
      throw error;
    }
  };

  // Handle summarization — delegates to parent's background summarizer
  const handleSummarize = () => {
    // Check if PDF is available for extraction
    if (!pdfUrlForExtract) {
      if ((isSemanticScholar || isCrossref || isEuropePmc || isPubmed || isDoaj || isUnpaywall) && abstract) {
        showToast('PDF not available for this paper. Summarization requires PDF access.', 'info');
      } else {
        showToast('No PDF URL available for this paper', 'error');
      }
      return;
    }

    // Check if already summarized or in progress
    if (summary || summarizing) {
      if (summary) {
        // Scroll to the existing summary
        setTimeout(() => {
          summaryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 150);
      }
      return;
    }

    // Delegate to the parent's background summarizer
    onStartSummarize(paper);
    showToast('Summarization started — you can browse other papers while it processes', 'info');
  };

  // Handle chat question
  const handleChatSubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userQuestion = chatInput.trim();
    setChatInput('');

    // Add user message to chat
    const userMessage = { role: 'user', content: userQuestion };
    setChatMessages(prev => [...prev, userMessage]);
    setChatLoading(true);

    try {
      // If we don't have pdfContent yet (no prior summarization), extract it first
      let currentPdfContent = pdfContent;
      let usedAbstractFallback = false;
      if (!currentPdfContent && pdfUrlForExtract) {
        showToast('Extracting paper content for the first time...', 'info');
        try {
          const extractResponse = await semanticScholarAPI.extractPdfContent(pdfUrlForExtract);
          if (extractResponse.status === 'success' && extractResponse.full_text) {
            currentPdfContent = extractResponse.full_text;
            setPdfContent(currentPdfContent);
          } else {
            console.info('No direct PDF available for extraction, using abstract for chat context.');
            if (abstract) {
              currentPdfContent = abstract;
              usedAbstractFallback = true;
            }
          }
        } catch {
          console.info('No direct PDF available for extraction, using abstract for chat context.');
          if (abstract) {
            currentPdfContent = abstract;
            usedAbstractFallback = true;
          }
        }
      } else if (!currentPdfContent && abstract) {
        // No PDF, but have abstract — use it as the paper content
        currentPdfContent = abstract;
        usedAbstractFallback = true;
      }

      if (!currentPdfContent && !pdfUrlForExtract) {
        showToast('No paper content available to answer questions about', 'error');
        setChatMessages(prev => prev.slice(0, -1));
        setChatLoading(false);
        return;
      }

      // Determine paper source for metadata
      const paperSource = isArxiv ? 'arXiv' : isCore ? 'CORE' : isPmc ? 'PMC'
        : isCrossref ? 'Crossref' : isEuropePmc ? 'Europe PMC' : isPubmed ? 'PubMed' : isDoaj ? 'DOAJ' : isUnpaywall ? 'Unpaywall' : isSemanticScholar ? 'Semantic Scholar' : 'Unknown';

      // Use unified chatAPI with Redis session persistence
      const response = await chatAPI.askQuestion(userQuestion, {
        // If we only have abstract fallback, still pass pdfUrl so backend can retry extraction.
        pdfText: usedAbstractFallback ? undefined : currentPdfContent,
        pdfUrl: pdfUrlForExtract || undefined,
        abstract: abstract || undefined,
        sessionId: chatSessionId || undefined,
        paperTitle: paper.title || undefined,
        paperSource: paperSource,
      });

      if (response.status === 'success' && response.answer) {
        // Store session_id for subsequent messages
        if (response.session_id) {
          setChatSessionId(response.session_id);
        }
        const assistantMessage = {
          role: 'assistant',
          content: response.answer,
          ...(response.paper_id ? { paperId: response.paper_id } : {}),
        };
        setChatMessages(prev => [...prev, assistantMessage]);
      } else {
        showToast('Failed to get answer', 'error');
        setChatMessages(prev => prev.slice(0, -1)); // Remove user message on error
      }
    } catch (error) {
      console.error('Error asking question:', error);
      showToast(`Failed to get answer: ${error.message}`, 'error');
      setChatMessages(prev => prev.slice(0, -1)); // Remove user message on error
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className={`fixed bg-white z-50 overflow-y-auto shadow-2xl transition-all duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] transform ${paper ? 'translate-x-0' : 'translate-x-full'} ${
      isSplitScreen
        ? 'top-4 bottom-4 right-4 w-[calc(50%-1rem)] rounded-2xl border border-gray-200'
        : 'top-0 bottom-0 right-0 w-full md:w-[600px] border-l border-gray-200'
    }`}>
      {/* Header */}
      <div className="sticky top-0 bg-white border-b border-gray-200 p-4 flex items-start justify-between">
        <div className="flex-1 pr-4">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-500 uppercase">Work</span>
          </div>
          <h2 className="text-xl font-semibold text-black leading-tight">
            {paper.title || 'Untitled Paper'}
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-gray-100 rounded transition-colors"
        >
          <X className="w-5 h-5 text-gray-600" />
        </button>
      </div>

      {/* Action Buttons */}
      <div className="p-4 border-b border-gray-200 flex flex-wrap gap-2">
        {htmlUrl && (
          <a
            href={htmlUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-black hover:bg-gray-800 text-white rounded text-sm flex items-center gap-2 transition-colors"
          >
            <FileText className="w-4 h-4" />
            HTML
          </a>
        )}
        {pdfUrlForExtract && (
          <a
            href={pdfUrlForExtract}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 bg-black hover:bg-gray-800 text-white rounded text-sm flex items-center gap-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            PDF
          </a>
        )}
        <button
          onClick={handleCopyJSON}
          className="px-4 py-2 bg-black hover:bg-gray-800 text-white rounded text-sm flex items-center gap-2 transition-colors"
          title="Copy paper data as JSON"
        >
          <Code className="w-4 h-4" />
          JSON
        </button>
        <div className="relative link-dropdown-container">
          <button
            onClick={() => setShowLinkDropdown(!showLinkDropdown)}
            className={`px-4 py-2 bg-black hover:bg-gray-800 text-white rounded text-sm flex items-center gap-2 transition-colors ${showLinkDropdown ? 'bg-gray-800' : ''}`}
            title="Copy URL or Share"
          >
            {copiedToClipboard ? (
              <CheckCircle className="w-4 h-4" />
            ) : (
              <Share2 className="w-4 h-4" />
            )}
            <span>Share</span>
            <ChevronDown className={`w-3 h-3 transition-transform ${showLinkDropdown ? 'rotate-180' : ''}`} />
          </button>
          {showLinkDropdown && (
            <div className="absolute top-full left-0 mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
              <button
                onClick={handleCopyURL}
                className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 text-gray-700"
              >
                <Copy className="w-4 h-4" />
                Copy URL
              </button>
              <button
                onClick={handleShare}
                className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 text-gray-700"
              >
                <Share2 className="w-4 h-4" />
                Share
              </button>
            </div>
          )}
        </div>
        <button
          onClick={isSaved ? handleOpenNotes : handleSaveArticle}
          className={`px-4 py-2 rounded text-sm flex items-center gap-2 transition-colors ${isSaved
            ? 'bg-gray-100 hover:bg-gray-200 text-black border border-gray-300'
            : 'bg-black hover:bg-gray-800 text-white'
            }`}
          title={isSaved ? 'View/Edit Notes' : 'Save Article'}
          disabled={loadingSaved}
        >
          {isSaved ? (
            <>
              <Bookmark className="w-4 h-4 fill-current" />
              <span>Saved</span>
            </>
          ) : (
            <>
              <Bookmark className="w-4 h-4" />
              <span>Save</span>
            </>
          )}
        </button>
        {isSaved && notes && (
          <button
            onClick={handleOpenNotes}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-black rounded text-sm flex items-center gap-2 transition-colors border border-gray-300"
            title="View Notes"
          >
            <FileText className="w-4 h-4" />
            Notes
          </button>
        )}
        {/* Show summarize button if: PDF available OR (Semantic Scholar/Crossref/Europe PMC/PubMed/DOAJ/Unpaywall paper with abstract) */}
        {(pdfUrlForExtract || (isSemanticScholar && abstract) || (isCrossref && abstract) || (isEuropePmc && abstract) || (isPubmed && abstract) || (isDoaj && abstract) || (isUnpaywall && abstract)) && (
          <>
            <button
              onClick={handleSummarize}
              disabled={summarizing || summary}
              className={`px-4 py-2 rounded text-sm flex items-center gap-2 transition-colors ${summary
                ? 'bg-gray-100 hover:bg-gray-200 text-black border border-gray-300'
                : 'bg-black hover:bg-gray-800 text-white'
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              title={summary ? 'Summary already generated' : pdfUrlForExtract ? 'Extract PDF and generate AI summary (local AI)' : ((isSemanticScholar || isCrossref || isEuropePmc || isPubmed || isDoaj || isUnpaywall) && abstract ? 'PDF not available - only abstract available' : 'Extract PDF and generate AI summary')}
            >
              {summarizing ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                  <span>Extracting & Summarizing...</span>
                </>
              ) : summary ? (
                <>
                  <CheckCircle className="w-4 h-4" />
                  <span>Summarized</span>
                </>
              ) : (
                <>
                  <MessageSquare className="w-4 h-4" />
                  <span>Summarize with AI</span>
                </>
              )}
            </button>

            {/* Ask about this paper — show if PDF or abstract is available */}
            {(pdfUrlForExtract || abstract) && (
              <button
                onClick={() => {
                  setShowChat(!showChat);
                  // Scroll to chat section after it opens
                  if (!showChat) {
                    setTimeout(() => {
                      chatRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 100);
                  }
                }}
                className={`px-4 py-2 rounded text-sm flex items-center gap-2 transition-colors ${showChat
                  ? 'bg-gray-100 hover:bg-gray-200 text-black border border-gray-300'
                  : 'bg-black hover:bg-gray-800 text-white'
                  }`}
                title="Ask questions about this paper"
              >
                <Bot className="w-4 h-4" />
                <span>Ask about this paper</span>
              </button>
            )}
            {/* Generate Draft button — only for papers with open-access PDF */}
            {pdfUrlForExtract && (
              <button
                onClick={async () => {
                  if (draft) {
                    draftRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    return;
                  }
                  setDraftGenerating(true);
                  setDraftProgress('Downloading & extracting PDF...');
                  try {
                    const authorsStr = Array.isArray(paper.authors)
                      ? paper.authors.map(a => typeof a === 'string' ? a : a.name || '').join(', ')
                      : '';
                    setDraftProgress('Extracting figures & analyzing visuals...');
                    const response = await draftAPI.generateDraft(pdfUrlForExtract, {
                      title: paper.title || '',
                      authors: authorsStr,
                      abstract: abstract || '',
                    });
                    if (response.status === 'success' && response.draft) {
                      setDraft(response.draft);
                      setDraftFigures(response.figure_analyses || []);
                      showToast(
                        `Draft generated! ${response.metadata?.figures_analyzed || 0} figures analyzed in ${response.metadata?.processing_time_seconds || '?'}s`,
                        'success'
                      );
                      setTimeout(() => {
                        draftRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                      }, 150);
                    } else {
                      showToast('Failed to generate draft', 'error');
                    }
                  } catch (error) {
                    console.error('Draft generation error:', error);
                    const msg = error.message || error.details?.message || 'Failed to generate draft.';
                    showToast(`Draft error: ${msg}`, 'error');
                  } finally {
                    setDraftGenerating(false);
                    setDraftProgress('');
                  }
                }}
                disabled={draftGenerating}
                className={`px-4 py-2 rounded text-sm flex items-center gap-2 transition-colors ${draft
                  ? 'bg-emerald-100 hover:bg-emerald-200 text-emerald-800 border border-emerald-300'
                  : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 text-white'
                  } disabled:opacity-60 disabled:cursor-not-allowed`}
                title={draft ? 'Scroll to generated draft' : 'Generate a research draft with AI figure analysis'}
              >
                {draftGenerating ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                    <span className="max-w-[180px] truncate">{draftProgress || 'Generating...'}</span>
                  </>
                ) : draft ? (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    <span>Draft Ready</span>
                  </>
                ) : (
                  <>
                    <PenLine className="w-4 h-4" />
                    <span>Generate Draft</span>
                  </>
                )}
              </button>
            )}
          </>
        )}
      </div>

      {/* Metadata */}
      <div className="p-4 space-y-4">
        {year && (
          <div>
            <span className="text-xs text-gray-500 uppercase">Year</span>
            <p className="text-black mt-1">{year}</p>
          </div>
        )}

        <div>
          <span className="text-xs text-gray-500 uppercase">Type</span>
          <p className="text-black mt-1">
            {paper.publicationTypes && paper.publicationTypes.length > 0
              ? paper.publicationTypes.join(', ')
              : 'Article'}
          </p>
        </div>

        {abstract && (
          <div>
            <span className="text-xs text-gray-500 uppercase">Abstract</span>
            <p className="text-gray-700 mt-1 leading-relaxed whitespace-pre-wrap">
              {abstractExpanded ? abstract : abstractPreview}
            </p>
            {abstract.length > 300 && (
              <button
                onClick={() => setAbstractExpanded(!abstractExpanded)}
                className="text-black hover:text-gray-700 text-sm mt-2 underline"
              >
                {abstractExpanded ? 'less' : 'more'}
              </button>
            )}
          </div>
        )}

        {venue && (
          <div>
            <span className="text-xs text-gray-500 uppercase">Source</span>
            <p className="text-black mt-1">{venue}</p>
          </div>
        )}

        {authors.length > 0 && (
          <div>
            <span className="text-xs text-gray-500 uppercase">Authors</span>
            <div className="mt-1 space-y-1">
              {authors.slice(0, 5).map((author, idx) => (
                <p key={idx} className="text-black">
                  {typeof author === 'string' ? author : author.name || author}
                </p>
              ))}
              {authors.length > 5 && (
                <button className="text-black hover:text-gray-700 text-sm underline">
                  +{authors.length - 5} more
                </button>
              )}
            </div>
          </div>
        )}

        <div>
          <span className="text-xs text-gray-500 uppercase">Language</span>
          <p className="text-black mt-1">English</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          {referenceCount > 0 && (
            <div>
              <span className="text-xs text-gray-500 uppercase">Cites</span>
              <p className="text-black mt-1">{referenceCount.toLocaleString()}</p>
            </div>
          )}
          {citationCount > 0 && (
            <div>
              <span className="text-xs text-gray-500 uppercase">Cited by</span>
              <p className="text-black mt-1">{citationCount.toLocaleString()}</p>
            </div>
          )}
        </div>

        {isOpenAccess && (
          <div>
            <span className="text-xs text-gray-500 uppercase">Open Access</span>
            <p className="text-black mt-1">Yes</p>
          </div>
        )}

        {fields.length > 0 && (
          <div>
            <span className="text-xs text-gray-500 uppercase">Topic</span>
            <div className="mt-1 flex flex-wrap gap-2">
              {fields.map((field, idx) => (
                <span
                  key={idx}
                  className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm border border-gray-300"
                >
                  {field}
                </span>
              ))}
            </div>
          </div>
        )}

        {doi && (
          <div>
            <span className="text-xs text-gray-500 uppercase">DOI</span>
            <a
              href={`https://doi.org/${doi}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-black hover:text-gray-700 mt-1 block underline"
            >
              {doi}
            </a>
          </div>
        )}

        {paper.url && paper.url !== 'N/A' && (
          <div>
            <span className="text-xs text-gray-500 uppercase">URL</span>
            <a
              href={paper.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-black hover:text-gray-700 mt-1 block break-all underline"
            >
              {paper.url}
            </a>
          </div>
        )}
      </div>

      {/* Chat Interface */}
      {showChat && (
        <div ref={chatRef} className="p-4 border-t-2 border-purple-300 bg-purple-50">
          <div className="flex items-center gap-2 mb-3">
            <Bot className="w-5 h-5 text-purple-600" />
            <h3 className="text-base font-semibold text-black">Ask about this paper</h3>
          </div>

          {/* Chat Messages */}
          <div className="bg-white border border-gray-200 rounded-lg p-4 max-h-[400px] overflow-y-auto mb-3 space-y-4">
            {chatMessages.length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-8">
                <Bot className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                <p>Ask any question about this research paper</p>
                <p className="text-xs mt-1">Example: "What is the main contribution?" or "Explain the methodology"</p>
              </div>
            ) : (
              chatMessages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                >
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${msg.role === 'user' ? 'bg-black text-white' : 'bg-purple-100 text-purple-600'
                    }`}>
                    {msg.role === 'user' ? (
                      <User className="w-4 h-4" />
                    ) : (
                      <Bot className="w-4 h-4" />
                    )}
                  </div>
                  <div className={`flex-1 ${msg.role === 'user' ? 'text-right' : 'text-left'}`}>
                    <div className={`inline-block p-3 rounded-lg max-w-[85%] ${msg.role === 'user'
                      ? 'bg-black text-white'
                      : 'bg-gray-100 text-gray-800'
                      }`}>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                      {msg.role === 'assistant' && msg.paperId && (
                        <p className="text-xs text-gray-500 mt-2 pt-2 border-t border-gray-200 font-mono break-all">
                          Paper hash id: {msg.paperId}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            {chatLoading && (
              <div className="flex gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-gray-100 rounded-lg p-3">
                  <div className="flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <form onSubmit={handleChatSubmit} className="flex gap-2">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask a question about this paper..."
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              disabled={chatLoading}
            />
            <button
              type="submit"
              disabled={!chatInput.trim() || chatLoading}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              <span>Send</span>
            </button>
          </form>
        </div>
      )}

      {/* AI Summary Display */}
      {summary && (
        <div ref={summaryRef} className="p-4 border-t-2 border-blue-300 bg-blue-50">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="w-5 h-5 text-blue-600" />
            <h3 className="text-base font-semibold text-black">AI Summary (Generated locally)</h3>
          </div>
          <div className="space-y-4">
            {summary.problem_statement && (
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Problem Statement</h4>
                <p className="text-sm text-gray-600 leading-relaxed">{summary.problem_statement}</p>
              </div>
            )}
            {summary.methodology && (
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Methodology</h4>
                <p className="text-sm text-gray-600 leading-relaxed">{summary.methodology}</p>
              </div>
            )}
            {summary.key_findings && (
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Key Findings</h4>
                <p className="text-sm text-gray-600 leading-relaxed">{summary.key_findings}</p>
              </div>
            )}
            {summary.conclusion && (
              <div className="bg-white border border-gray-200 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Conclusion</h4>
                <p className="text-sm text-gray-600 leading-relaxed">{summary.conclusion}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Generated Draft Display */}
      {draft && (
        <div ref={draftRef} className="p-4 border-t-2 border-emerald-300 bg-emerald-50">
          <div className="flex items-center justify-between mb-2">
            <button
              onClick={() => setDraftMinimized(prev => !prev)}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity"
              title={draftMinimized ? 'Expand draft' : 'Minimize draft'}
            >
              <PenLine className="w-5 h-5 text-emerald-600" />
              <h3 className="text-base font-semibold text-black">AI Research Draft</h3>
              {draftFigures.length > 0 && (
                <span className="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full font-medium">
                  {draftFigures.length} figures analyzed
                </span>
              )}
              {draftMinimized ? (
                <ChevronDown className="w-4 h-4 text-gray-500" />
              ) : (
                <ChevronUp className="w-4 h-4 text-gray-500" />
              )}
            </button>
            {!draftMinimized && (
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    const sections = [
                      draft.introduction && `# Introduction\n\n${draft.introduction}`,
                      draft.literature_context && `# Literature Context\n\n${draft.literature_context}`,
                      draft.methodology_overview && `# Methodology Overview\n\n${draft.methodology_overview}`,
                      draft.key_analysis && `# Key Analysis\n\n${draft.key_analysis}`,
                      draft.figure_discussions && draft.figure_discussions !== 'No figures available' && `# Figure Discussions\n\n${draft.figure_discussions}`,
                      draft.conclusion && `# Conclusion\n\n${draft.conclusion}`,
                    ].filter(Boolean).join('\n\n---\n\n');

                    const figureSection = draftFigures.length > 0
                      ? '\n\n---\n\n# Figure Analyses\n\n' + draftFigures.map((f, i) =>
                        `## Figure ${f.figure_number || i + 1} (Page ${f.page_number || '?'})\nType: ${f.chart_type || 'Unknown'}\nDescription: ${f.description || 'N/A'}\nInsights: ${f.data_insights || 'N/A'}`
                      ).join('\n\n')
                      : '';

                    navigator.clipboard.writeText(sections + figureSection);
                    showToast('Draft copied to clipboard', 'success');
                  }}
                  className="p-1.5 hover:bg-emerald-100 rounded transition-colors"
                  title="Copy draft to clipboard"
                >
                  <ClipboardCopy className="w-4 h-4 text-emerald-600" />
                </button>
                <button
                  onClick={() => {
                    const sections = [
                      draft.introduction && `INTRODUCTION\n\n${draft.introduction}`,
                      draft.literature_context && `LITERATURE CONTEXT\n\n${draft.literature_context}`,
                      draft.methodology_overview && `METHODOLOGY OVERVIEW\n\n${draft.methodology_overview}`,
                      draft.key_analysis && `KEY ANALYSIS\n\n${draft.key_analysis}`,
                      draft.figure_discussions && draft.figure_discussions !== 'No figures available' && `FIGURE DISCUSSIONS\n\n${draft.figure_discussions}`,
                      draft.conclusion && `CONCLUSION\n\n${draft.conclusion}`,
                    ].filter(Boolean).join('\n\n' + '='.repeat(60) + '\n\n');

                    const blob = new Blob([sections], { type: 'text/plain' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `draft_${(paper.title || 'untitled').slice(0, 40).replace(/[^a-zA-Z0-9]/g, '_')}.txt`;
                    a.click();
                    URL.revokeObjectURL(url);
                    showToast('Draft downloaded as .txt', 'success');
                  }}
                  className="p-1.5 hover:bg-emerald-100 rounded transition-colors"
                  title="Download draft as .txt"
                >
                  <Download className="w-4 h-4 text-emerald-600" />
                </button>
              </div>
            )}
          </div>

          {!draftMinimized && (
            <>
              <div className="space-y-3 mt-2">
                {[
                  { key: 'introduction', label: 'Introduction', icon: '📖' },
                  { key: 'literature_context', label: 'Literature Context', icon: '📚' },
                  { key: 'methodology_overview', label: 'Methodology Overview', icon: '🔬' },
                  { key: 'key_analysis', label: 'Key Analysis', icon: '📊' },
                  { key: 'figure_discussions', label: 'Figure Discussions', icon: '🖼️' },
                  { key: 'conclusion', label: 'Conclusion', icon: '✅' },
                ].map(({ key, label, icon }) => {
                  const content = draft[key];
                  if (!content || content === 'No figures available') return null;
                  const isCollapsed = draftCollapsed[key];
                  return (
                    <div key={key} className="bg-white border border-gray-200 rounded-lg overflow-hidden">
                      <button
                        onClick={() => setDraftCollapsed(prev => ({ ...prev, [key]: !prev[key] }))}
                        className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span>{icon}</span>
                          <h4 className="text-sm font-semibold text-gray-800">{label}</h4>
                        </div>
                        {isCollapsed ? <Eye className="w-4 h-4 text-gray-400" /> : <EyeOff className="w-4 h-4 text-gray-400" />}
                      </button>
                      {!isCollapsed && (
                        <div className="px-4 pb-4">
                          <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{content}</p>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Figure Analyses */}
                {draftFigures.length > 0 && (
                  <div className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <Image className="w-4 h-4 text-emerald-600" />
                      <h4 className="text-sm font-semibold text-gray-800">Figure Analysis Details</h4>
                    </div>
                    <div className="space-y-3">
                      {draftFigures.map((fig, idx) => (
                        <div key={idx} className="border border-emerald-100 bg-emerald-50/50 rounded-lg p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-bold bg-emerald-200 text-emerald-800 px-2 py-0.5 rounded">
                              Figure {fig.figure_number || idx + 1}
                            </span>
                            <span className="text-xs text-gray-500">Page {fig.page_number || '?'}</span>
                            <span className="text-xs text-emerald-600 font-medium">{fig.chart_type || 'Unknown'}</span>
                          </div>
                          {fig.description && (
                            <p className="text-sm text-gray-700 mb-1"><strong>Description:</strong> {fig.description}</p>
                          )}
                          {fig.data_insights && (
                            <p className="text-sm text-gray-600"><strong>Insights:</strong> {fig.data_insights}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-3 text-center">
                <p className="text-[10px] text-emerald-400">Generated by GPT-4o with Vision — review and edit before use</p>
              </div>
            </>
          )}
        </div>
      )}



      {/* Toast Container */}
      <ToastContainer toasts={toasts} removeToast={removeToast} />

      {/* Notes Modal */}
      <ArticleNotesModal
        isOpen={showNotesModal}
        onClose={() => setShowNotesModal(false)}
        paper={paper}
        notes={notes}
        onSave={handleSaveNotes}
      />
    </div>
  );
};

// =====================================================
// Cross-API Deduplication Utility
// =====================================================
// Papers from 6 different APIs often refer to the same work.
// This utility detects duplicates using DOI and title similarity,
// and merges them to keep the richest metadata.

/**
 * Normalize a paper title for comparison.
 * Strips punctuation, collapses whitespace, lowercases.
 */
const normalizeTitle = (title) => {
  if (!title) return '';
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')  // Remove all non-alphanumeric except spaces
    .replace(/\s+/g, ' ')          // Collapse multiple spaces
    .trim();
};

/**
 * Extract a DOI string from a paper object, checking multiple possible locations.
 * Returns a normalized lowercase DOI string, or null.
 */
const extractDOI = (paper) => {
  // Check externalIds.DOI or externalIds.doi
  const extDoi = paper.externalIds?.DOI || paper.externalIds?.doi;
  if (extDoi) return extDoi.toLowerCase().replace(/^https?:\/\/doi\.org\//i, '');

  // Check paper.doi (some APIs like CORE, PMC set this directly)
  if (paper.doi) {
    const d = paper.doi.toLowerCase().replace(/^https?:\/\/doi\.org\//i, '');
    if (d && d.length > 3) return d;
  }

  // Check URL for DOI patterns
  if (paper.url && paper.url.includes('doi.org/')) {
    const match = paper.url.match(/doi\.org\/(.+)/i);
    if (match) return match[1].toLowerCase();
  }

  return null;
};

/**
 * Score a paper's metadata richness. Higher = better record to keep.
 */
const scorePaperRichness = (paper) => {
  let score = 0;
  if (paper.abstract && paper.abstract !== 'N/A' && paper.abstract.length > 50) score += 3;
  if (paper.citationCount > 0) score += 2;
  if (paper.year) score += 1;
  if (paper.openAccessPdf || paper.pdf_url) score += 2;
  if (paper.isOpenAccess) score += 1;
  if (paper.authors && paper.authors.length > 0) score += 1;
  if (paper.venue && paper.venue !== 'N/A') score += 1;
  if (paper.fieldsOfStudy && paper.fieldsOfStudy.length > 0) score += 1;
  if (paper.publicationTypes && paper.publicationTypes.length > 0) score += 1;
  if (paper.externalIds && Object.keys(paper.externalIds).length > 0) score += 1;
  if (paper.institutions && paper.institutions.length > 0) score += 1;
  if (paper.referenceCount > 0) score += 1;
  return score;
};

/**
 * Merge two duplicate papers, keeping the richer data and combining sources.
 * `existing` is the paper already in results, `incoming` is the new one.
 */
const mergePapers = (existing, incoming) => {
  const existingScore = scorePaperRichness(existing);
  const incomingScore = scorePaperRichness(incoming);

  // Start with the richer record as base
  const base = incomingScore > existingScore ? { ...incoming } : { ...existing };
  const other = incomingScore > existingScore ? existing : incoming;

  // Combine sources into an array
  const existingSources = existing.allSources || [existing.source || 'Unknown'];
  const incomingSource = incoming.source || 'Unknown';
  const allSources = [...new Set([...existingSources, incomingSource])];
  base.allSources = allSources;

  // Keep the best "source" label (primary source for display)
  // Prefer the base's source since it's the richer record

  // Fill in missing fields from the other record
  if (!base.abstract || base.abstract === 'N/A' || base.abstract.length < 50) {
    if (other.abstract && other.abstract !== 'N/A' && other.abstract.length > 50) {
      base.abstract = other.abstract;
    }
  }
  if (!base.openAccessPdf && other.openAccessPdf) base.openAccessPdf = other.openAccessPdf;
  if (!base.pdf_url && other.pdf_url) base.pdf_url = other.pdf_url;
  if (!base.year && other.year) base.year = other.year;
  if (!base.venue || base.venue === 'N/A') base.venue = other.venue || base.venue;
  if ((!base.citationCount || base.citationCount === 0) && other.citationCount > 0) {
    base.citationCount = other.citationCount;
  }
  if ((!base.referenceCount || base.referenceCount === 0) && other.referenceCount > 0) {
    base.referenceCount = other.referenceCount;
  }
  if ((!base.fieldsOfStudy || base.fieldsOfStudy.length === 0) && other.fieldsOfStudy?.length > 0) {
    base.fieldsOfStudy = other.fieldsOfStudy;
  }
  if ((!base.publicationTypes || base.publicationTypes.length === 0) && other.publicationTypes?.length > 0) {
    base.publicationTypes = other.publicationTypes;
  }
  if ((!base.institutions || base.institutions.length === 0) && other.institutions?.length > 0) {
    base.institutions = other.institutions;
  }
  if (!base.isOpenAccess && other.isOpenAccess) base.isOpenAccess = true;

  // Merge externalIds
  if (other.externalIds) {
    base.externalIds = { ...(other.externalIds || {}), ...(base.externalIds || {}) };
  }

  return base;
};

/**
 * Deduplicate an array of papers using DOI and normalized title matching.
 * Returns a new array with duplicates merged.
 *
 * @param {Array} papers - Array of paper objects from multiple APIs
 * @returns {Array} Deduplicated array of papers
 */
const deduplicatePapers = (papers) => {
  if (!papers || papers.length === 0) return [];

  const doiMap = new Map();       // DOI → index in result array
  const titleMap = new Map();     // normalized title → index in result array
  const result = [];

  let dupeCount = 0;

  for (const paper of papers) {
    const doi = extractDOI(paper);
    const normTitle = normalizeTitle(paper.title);

    // Strategy 1: Check DOI match
    if (doi && doiMap.has(doi)) {
      const existingIdx = doiMap.get(doi);
      result[existingIdx] = mergePapers(result[existingIdx], paper);
      dupeCount++;
      continue;
    }

    // Strategy 2: Check normalized title match
    if (normTitle && normTitle.length > 10 && titleMap.has(normTitle)) {
      const existingIdx = titleMap.get(normTitle);
      result[existingIdx] = mergePapers(result[existingIdx], paper);
      // Also register DOI if the incoming paper has one
      if (doi) doiMap.set(doi, existingIdx);
      dupeCount++;
      continue;
    }

    // No match — new unique paper
    const idx = result.length;
    // Initialize allSources
    paper.allSources = [paper.source || 'Unknown'];
    result.push(paper);

    if (doi) doiMap.set(doi, idx);
    if (normTitle && normTitle.length > 10) titleMap.set(normTitle, idx);
  }

  if (dupeCount > 0) {
    console.log(`🔄 Deduplication: removed ${dupeCount} duplicates (${papers.length} → ${result.length})`);
  }

  return result;
};

// Filter criteria structure
const createFilter = (field, operator, value) => ({
  id: Date.now() + Math.random(),
  field,
  operator,
  value
});

export default function Results() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const topic = searchParams.get('topic');
  const { recordSearch } = useSearchHistory();

  const [allPapers, setAllPapers] = useState([]); // All fetched papers
  const [papers, setPapers] = useState([]); // Filtered papers
  const [loading, setLoading] = useState(true);
  const [fetchProgress, setFetchProgress] = useState(0); // 0-100 for YouTube-style progress bar
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [selectedPaper, setSelectedPaper] = useState(null);
  const [unpaywallPdfUrl, setUnpaywallPdfUrl] = useState(null);
  const [showStatsPanel, setShowStatsPanel] = useState(true);
  // True when the AI model backend is unreachable: search still
  // works, but summarize / chat / draft will not. Shown as a banner
  // instead of letting those actions hang or fail silently.
  const [aiDown, setAiDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    checkAiReady().then((ok) => {
      if (!cancelled) setAiDown(!ok);
    });
    return () => { cancelled = true; };
  }, []);

  // Resolve an open-access PDF via Unpaywall when the selected paper
  // carries a DOI but no PDF link. Unpaywall is DOI-based, so it never
  // joins the keyword search dispatch; this lookup runs once per
  // selection and the resolved URL is passed to DetailPanel, where it
  // feeds pdfUrlForExtract (PDF link, extract, chat, draft and
  // summarize all use it).
  useEffect(() => {
    let cancelled = false;
    setUnpaywallPdfUrl(null);
    if (!selectedPaper) return undefined;
    const paperPdf = selectedPaper.pdf_url || selectedPaper.openAccessPdf ||
      (selectedPaper.url && selectedPaper.url.toLowerCase().endsWith('.pdf') ? selectedPaper.url : null);
    if (paperPdf) return undefined;
    const doiValue = extractDOI(selectedPaper);
    if (!doiValue) return undefined;
    unpaywallAPI.searchPapers(doiValue).then((res) => {
      if (cancelled) return;
      const found = res && res.status === 'success' && res.papers && res.papers[0];
      if (found && found.pdf_url) setUnpaywallPdfUrl(found.pdf_url);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [selectedPaper]);
  const [showCitationMesh, setShowCitationMesh] = useState(false);
  const citationNetworkCache = React.useRef(null); // Persists network data across open/close
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 20;

  // Sorting state
  const [sortOption, setSortOption] = useState('relevance');
  const [showSortDropdown, setShowSortDropdown] = useState(false);

  // Export dropdown state
  const [showExportDropdown, setShowExportDropdown] = useState(false);

  // Sorting options configuration
  const sortOptions = [
    { value: 'relevance', label: 'Relevance' },
    { value: 'citations', label: 'Citation Count' },
    { value: 'title', label: 'Title' },
    { value: 'year', label: 'Year' },
  ];

  // Query builder state — starts empty since APIs already handle relevance search
  // Users can add manual filters to narrow down if needed
  const [filters, setFilters] = useState([]);
  const [searchQuery, setSearchQuery] = useState(topic || '');

  // Stats panel filter state
  const [selectedYears, setSelectedYears] = useState([]);
  const [selectedTopics, setSelectedTopics] = useState([]);
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [selectedInstitutions, setSelectedInstitutions] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);
  const [openAccessOnly, setOpenAccessOnly] = useState(false);
  const [fullContentOnly, setFullContentOnly] = useState(false);
  const [fromCache, setFromCache] = useState(false);

  // ===== Background Summarization State =====
  // Map<paperId, { paperId, paper, status, summary, fullText, error, startedAt }>
  const [summaryJobs, setSummaryJobs] = useState(new Map());
  const { toasts: resultToasts, showToast: showResultToast, removeToast: removeResultToast } = useToast();

  /**
   * Start a background summarization job for a paper.
   * The API call runs independently of the DetailPanel lifecycle,
   * so closing the panel does NOT cancel the operation.
   */
  const startBackgroundSummarize = useCallback(async (paper) => {
    const id = paper.paperId || paper.id || paper.arxiv_id || paper.core_id || paper.pmc_id || paper.semantic_scholar_id || paper.crossref_id || paper.europe_pmc_id || paper.pubmed_id || paper.doaj_id || paper.unpaywall_id;
    if (!id) return;

    // Don't start if already loading or done
    const existing = summaryJobs.get(id);
    if (existing && (existing.status === 'loading' || existing.status === 'done')) return;

    // Add the job as loading
    setSummaryJobs(prev => {
      const next = new Map(prev);
      next.set(id, {
        paperId: id,
        paper: paper,
        status: 'loading',
        summary: null,
        fullText: null,
        error: null,
        startedAt: Date.now(),
      });
      return next;
    });

    // Determine the correct API
    const isArxiv = paper.source === 'arXiv' || paper.arxiv_id;
    const isCore = paper.source === 'CORE' || paper.core_id;
    const isPmc = paper.source === 'PMC' || paper.pmc_id;
    const isSemanticScholar = paper.source === 'Semantic Scholar' || (paper.semantic_scholar_id && !isArxiv && !isCore && !isPmc);
    const isCrossref = paper.source === 'Crossref' || paper.crossref_id;
    const isEuropePmc = paper.source === 'Europe PMC' || paper.europe_pmc_id || paper.pmcid;
    const isPubmed = paper.source === 'PubMed' || paper.pubmed_id || paper.pmid;
    const isDoaj = paper.source === 'DOAJ' || paper.doaj_id;
    const isUnpaywall = paper.source === 'Unpaywall' || paper.unpaywall_id;
    const pdfUrl = paper.pdf_url || paper.openAccessPdf || (paper.url && paper.url.toLowerCase().endsWith('.pdf') ? paper.url : null);
    const arxivId = paper.arxiv_id;
    const title = paper.title || "";
    const abstract = paper.abstract || paper.snippet || "";
    const pmcId = paper.pmc_id || null;
    const doi = paper.doi || null;

    try {
      let response;
      if (isArxiv) {
        response = await arxivAPI.summarizePaper(arxivId || null, pdfUrl || null, title, abstract);
      } else if (isCore) {
        response = await coreAPI.summarizePaper(pdfUrl, title, abstract);
      } else if (isPmc) {
        response = await pmcAPI.summarizePaper(pdfUrl, pmcId, title, abstract);
      } else if (isSemanticScholar) {
        response = await semanticScholarAPI.summarizePaper(pdfUrl, title, abstract);
      } else if (isCrossref) {
        response = await crossrefAPI.summarizePaper(pdfUrl, title, abstract, doi);
      } else if (isEuropePmc) {
        response = await europePmcAPI.summarizePaper(pdfUrl, title, abstract, doi);
      } else if (isPubmed) {
        response = await pubmedAPI.summarizePaper(pdfUrl, title, abstract, doi);
      } else if (isDoaj) {
        response = await doajAPI.summarizePaper(pdfUrl, title, abstract, doi);
      } else if (isUnpaywall) {
        response = await unpaywallAPI.summarizePaper(pdfUrl, title, abstract, doi);
      } else {
        response = await semanticScholarAPI.summarizePaper(pdfUrl, title, abstract);
      }

      if (response.status === 'success' && response.summary) {
        setSummaryJobs(prev => {
          const next = new Map(prev);
          next.set(id, {
            ...prev.get(id),
            status: 'done',
            summary: response.summary,
            fullText: response.full_text || null,
          });
          return next;
        });

        if (response.fallback) {
          showResultToast(`Summary (from abstract): "${(paper.title || 'Paper').substring(0, 40)}…"`, 'warning', 6000);
        } else {
          showResultToast(`Summary ready: "${(paper.title || 'Paper').substring(0, 50)}…"`, 'success', 5000);
        }
      } else {
        throw new Error('Failed to generate summary');
      }
    } catch (error) {
      console.error('Background summarization error:', error);
      const errorMsg = error.message || error.details?.message || 'Summarization failed';
      setSummaryJobs(prev => {
        const next = new Map(prev);
        next.set(id, {
          ...prev.get(id),
          status: 'error',
          error: errorMsg,
        });
        return next;
      });
      showResultToast(`Summary failed: "${(paper.title || 'Paper').substring(0, 40)}…" — ${errorMsg}`, 'error', 5000);
    }
  }, [summaryJobs, showResultToast]);

  /**
   * Open the detail panel for a paper from a floating bubble click.
   */
  const handleBubbleClick = useCallback((paperId) => {
    const job = summaryJobs.get(paperId);
    if (job?.paper) {
      setSelectedPaper(job.paper);
    }
  }, [summaryJobs]);

  /**
   * Dismiss a summary job bubble.
   */
  const handleBubbleDismiss = useCallback((paperId) => {
    setSummaryJobs(prev => {
      const next = new Map(prev);
      next.delete(paperId);
      return next;
    });
  }, []);

  // Related searches state (fetched here, passed to StatsPanel)
  const [relatedSearches, setRelatedSearches] = useState([]);
  const [relatedLoading, setRelatedLoading] = useState(false);

  // Fetch related searches from OpenAlex when topic changes
  useEffect(() => {
    const fetchRelated = async () => {
      if (!topic || topic.trim().length < 2) {
        setRelatedSearches([]);
        return;
      }
      setRelatedLoading(true);
      try {
        // Use a shortened query (first 3 words) for broader results
        const words = topic.trim().split(/\s+/);
        const shortQuery = words.slice(0, Math.min(3, words.length)).join(' ');

        // Try autocomplete first with shortened query
        const autocompleteRes = await fetch(
          `https://api.openalex.org/autocomplete/topics?q=${encodeURIComponent(shortQuery)}`
        );

        let items = [];
        if (autocompleteRes.ok) {
          const data = await autocompleteRes.json();
          items = (data.results || [])
            .filter(t => t.display_name.toLowerCase() !== topic.trim().toLowerCase())
            .slice(0, 8)
            .map(t => ({
              text: t.display_name,
              hint: t.hint || '',
            }));
        }

        // If autocomplete returned too few, supplement with topics search
        if (items.length < 4) {
          const searchRes = await fetch(
            `https://api.openalex.org/topics?search=${encodeURIComponent(topic.trim())}&per-page=10&select=display_name,works_count`
          );
          if (searchRes.ok) {
            const searchData = await searchRes.json();
            const existing = new Set(items.map(i => i.text.toLowerCase()));
            existing.add(topic.trim().toLowerCase());
            const extra = (searchData.results || [])
              .filter(t => !existing.has(t.display_name.toLowerCase()))
              .slice(0, 8 - items.length)
              .map(t => ({
                text: t.display_name,
                hint: t.works_count ? `${Number(t.works_count).toLocaleString()} papers` : '',
              }));
            items = [...items, ...extra];
          }
        }

        setRelatedSearches(items);
      } catch (err) {
        console.warn('Related searches error:', err);
      } finally {
        setRelatedLoading(false);
      }
    };
    fetchRelated();
  }, [topic]);

  // Check if papers exist in Supabase for this topic (with 3-day freshness check)
  const CACHE_MAX_AGE_DAYS = 3;

  const checkCache = async (query) => {
    const normalizedQuery = query?.toLowerCase().trim() || '';
    console.log('Checking Supabase for topic:', normalizedQuery);

    try {
      const { data, error } = await supabase
        .from('research_papers')
        .select('*')
        .eq('topic', normalizedQuery)
        .limit(100);

      if (error) {
        console.log('Supabase lookup error:', error.message);
        return null;
      }

      if (!data || data.length === 0) {
        console.log('No papers found in Supabase for this topic');
        return null;
      }

      // Check freshness - use the most recent inserted_at
      const mostRecent = data.reduce((latest, row) => {
        const rowDate = new Date(row.inserted_at);
        return rowDate > latest ? rowDate : latest;
      }, new Date(0));

      const ageInDays = (Date.now() - mostRecent.getTime()) / (1000 * 60 * 60 * 24);
      console.log('Cache age:', ageInDays.toFixed(1), 'days');

      if (ageInDays > CACHE_MAX_AGE_DAYS) {
        console.log('Cache is stale (>', CACHE_MAX_AGE_DAYS, 'days), fetching fresh data');
        // Keep old data, will add new data alongside it
        return null;
      }

      console.log('Found fresh papers in Supabase:', data.length);

      // Map database columns back to expected paper format
      const papers = data.map(row => ({
        paperId: row.paperid,
        title: row.title,
        abstract: row.abstract,
        authors: row.authors,
        year: row.year,
        venue: row.venue,
        citationCount: row.citationcount,
        referenceCount: row.referencecount,
        url: row.url,
        openAccessPdf: row.openaccesspdf,
        isOpenAccess: row.isopenaccess,
        fieldsOfStudy: row.fieldsofstudy,
        publicationTypes: row.publicationtypes,
        institutions: row.institutions || [],  // Handle institutions field
        externalIds: row.externalids,
        source: row.source
      }));

      return { papers, results_count: papers.length };
    } catch (err) {
      console.log('Supabase unavailable:', err.message);
      return null;
    }
  };

  // Save papers to Supabase after fetching from API
  const saveToCache = async (query, papers) => {
    const normalizedQuery = query?.toLowerCase().trim() || '';
    console.log('Saving papers to Supabase:', papers.length, 'for topic:', normalizedQuery);

    try {
      // Map papers to match your table columns
      const papersToSave = papers.map(paper => ({
        paperid: paper.paperId || paper.id,
        title: paper.title,
        abstract: paper.abstract,
        authors: paper.authors,
        year: paper.year,
        venue: paper.venue,
        citationcount: paper.citationCount,
        referencecount: paper.referenceCount,
        url: paper.url,
        openaccesspdf: paper.openAccessPdf,
        isopenaccess: paper.isOpenAccess,
        fieldsofstudy: paper.fieldsOfStudy,
        publicationtypes: paper.publicationTypes,
        institutions: paper.institutions || [],  // Include institutions field
        externalids: paper.externalIds,
        source: paper.source || 'OpenAlex',
        topic: normalizedQuery,
        inserted_at: new Date().toISOString()
      }));

      const { error } = await supabase
        .from('research_papers')
        .insert(papersToSave);

      if (error) {
        console.log('Error saving to Supabase:', error.message);
      } else {
        console.log('Successfully saved', papers.length, 'papers to Supabase');
      }
    } catch (err) {
      console.log('Save to Supabase failed:', err.message);
    }
  };

  const fetchPapers = async (skipCache = false) => {
    setLoading(true);
    setError(null);
    setSelectedPaper(null);
    setFromCache(false);
    setFetchProgress(5); // Start at 5% to show something instantly

    try {
      // === OPTIMIZATION: Start cache check AND all API calls simultaneously ===
      // Instead of: check cache → wait → if miss → call APIs (sequential)
      // We do:      check cache + call APIs all at once (parallel)
      // If cache hits, we use cached data and ignore API results.

      const cachePromise = skipCache ? Promise.resolve(null) : checkCache(topic);

      // Prepare all API calls (they start immediately, don't wait for cache)
      const apiCalls = [
        { name: 'OpenAlex', promise: searchAPI.fetchPapers(topic, 30).catch(err => ({ status: 'error', error: err })) },
        { name: 'arXiv', promise: arxivAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'CORE', promise: coreAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'PMC', promise: pmcAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'Semantic Scholar', promise: semanticScholarAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'Crossref', promise: crossrefAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'Europe PMC', promise: europePmcAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'PubMed', promise: pubmedAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
        { name: 'DOAJ', promise: doajAPI.searchPapers(topic, 20).catch(err => ({ status: 'error', error: err })) },
      ];
      // Unpaywall is DOI-based with no keyword search, so it does not
      // join the dispatch above. It resolves OA PDFs per paper by DOI
      // in the detail panel (see the Unpaywall lookup effect there).

      // Check cache result first
      const cachedData = await cachePromise;

      if (cachedData && cachedData.papers && cachedData.papers.length > 0) {
        console.log('Using cached results:', cachedData.papers.length, 'papers');
        setAllPapers(cachedData.papers);
        setPapers(cachedData.papers);
        setStats({
          total: cachedData.results_count,
          sources: ['Cache']
        });
        setFromCache(true);
        setLoading(false);
        return; // API calls were started but we ignore their results
      }

      // === OPTIMIZATION: Progressive Loading ===
      // Show results from each API as soon as it resolves, instead of
      // waiting for ALL 9 keyword sources to finish. User sees first results in 1-2 sec.
      console.log('No cache found, fetching from all APIs with progressive loading...');

      let progressivePapers = [];
      const sources = [];
      let completedCount = 0;

      // Process each API result as it arrives
      const processResult = (name, result) => {
        completedCount++;
        // Each of 10 sources contributes ~9%, starting from 5% (9 keyword sources plus Unpaywall DOI lookup)
        setFetchProgress(Math.min(5 + Math.round((completedCount / apiCalls.length) * 90), 95));
        console.log(`[${completedCount}/10] ${name} completed:`, {
          status: result?.status,
          paperCount: result?.papers?.length || 0,
          hasError: !!result?.error,
          resultKeys: result ? Object.keys(result) : 'null'
        });

        if (result && result.status === 'success' && result.papers && result.papers.length > 0) {
          // Add new papers to the raw list
          progressivePapers = [...progressivePapers, ...result.papers];
          sources.push(name);

          // Deduplicate across all sources accumulated so far
          const deduplicated = deduplicatePapers(progressivePapers);
          console.log(`✅ ${name}: ${result.papers.length} papers (raw total: ${progressivePapers.length}, unique: ${deduplicated.length})`);

          // Update UI immediately with deduplicated results
          setAllPapers([...deduplicated]);
          setPapers([...deduplicated]);
          setStats({
            total: deduplicated.length,
            sources: [...sources]
          });

          // Stop showing full-screen loader after first results arrive
          if (completedCount <= apiCalls.length) {
            setLoading(false);
          }
        } else {
          console.warn(`⚠️ ${name}: No papers returned (status: ${result?.status}, message: ${result?.message || 'N/A'})`);
        }
      };

      // Await all API calls using allSettled, but process each as it completes
      await Promise.allSettled(
        apiCalls.map(({ name, promise }) =>
          promise.then(result => {
            processResult(name, result);
            return { name, result };
          }).catch(err => {
            completedCount++;
            console.error(`❌ ${name} FAILED:`, err.message || err);
            return { name, result: null, error: err };
          })
        )
      );

      // Final state update after all APIs complete — do one last dedup pass
      if (progressivePapers.length > 0) {
        const finalDeduplicated = deduplicatePapers(progressivePapers);
        console.log(`All APIs complete. Raw: ${progressivePapers.length}, Unique: ${finalDeduplicated.length} (removed ${progressivePapers.length - finalDeduplicated.length} duplicates)`);
        setAllPapers([...finalDeduplicated]);
        setPapers([...finalDeduplicated]);
        setStats({
          total: finalDeduplicated.length,
          sources: [...sources]
        });

        // Save deduplicated papers to cache (don't await — let it run in background)
        saveToCache(topic, finalDeduplicated).catch(err =>
          console.log('Background cache save failed:', err.message)
        );
      } else {
        setError('No papers found. Please try a different search term.');
        setAllPapers([]);
        setPapers([]);
      }
    } catch (err) {
      console.error('Error fetching papers:', err);
      if (err instanceof APIError) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setLoading(false);
      // Animate to 100% then fade out
      setFetchProgress(100);
      setTimeout(() => setFetchProgress(0), 600);
    }
  };

  // Sort papers function (priority: open access + has PDF to the top)
  const sortPapers = useCallback((papersToSort, sortBy) => {
    const sorted = [...papersToSort];

    const getPriority = (p) => {
      const hasPdf =
        Boolean(p.openAccessPdf) ||
        (p.url && typeof p.url === 'string' && p.url.toLowerCase().endsWith('.pdf'));
      const isOA = Boolean(p.isOpenAccess);
      // Priority 2: OA + PDF, 1: either, 0: neither
      return (isOA ? 1 : 0) + (hasPdf ? 1 : 0);
    };

    sorted.sort((a, b) => {
      const priorityDiff = getPriority(b) - getPriority(a);
      if (priorityDiff !== 0) return priorityDiff;

      switch (sortBy) {
        case 'citations':
          return (b.citationCount || 0) - (a.citationCount || 0);
        case 'year':
          return (b.year || 0) - (a.year || 0);
        case 'title':
          return (a.title || '').localeCompare(b.title || '');
        case 'relevance':
        default:
          return 0; // keep original order when equal priority
      }
    });

    return sorted;
  }, []);

  const applyFilters = useCallback(() => {
    console.log('applyFilters called:', { allPapersCount: allPapers.length });

    if (allPapers.length === 0) {
      console.log('No papers to filter');
      setPapers([]);
      return;
    }

    let filtered = [...allPapers];
    let hasActiveFilters = false;
    console.log('Starting with', filtered.length, 'papers');

    // Apply query builder filters
    filters.forEach(filter => {
      const filterValue = filter.value ? filter.value.toString().trim() : '';
      if (!filterValue) return; // Skip empty filters

      hasActiveFilters = true;

      if (filter.field === 'title_abstract') {
        const searchTerm = filter.value.toLowerCase();
        if (filter.operator === 'includes') {
          // Word-level matching: ALL words must appear in title OR abstract
          // This prevents the exact-phrase problem where "graph neural network security"
          // wouldn't match a paper about "security of graph neural networks"
          const words = searchTerm.split(/\s+/).filter(w => w.length > 1);
          filtered = filtered.filter(p => {
            const text = ((p.title || '') + ' ' + (p.abstract || '')).toLowerCase();
            return words.every(word => text.includes(word));
          });
        } else if (filter.operator === 'equals') {
          filtered = filtered.filter(p =>
            (p.title && p.title.toLowerCase() === searchTerm) ||
            (p.abstract && p.abstract.toLowerCase() === searchTerm)
          );
        }
      } else if (filter.field === 'open_access' && filter.operator === 'is') {
        if (filter.value.toLowerCase().includes('open access')) {
          filtered = filtered.filter(p => p.isOpenAccess === true);
        }
      } else if (filter.field === 'year') {
        const yearValue = parseInt(filter.value);
        if (!isNaN(yearValue)) {
          if (filter.operator === 'is') {
            filtered = filtered.filter(p => p.year === yearValue);
          } else if (filter.operator === '>') {
            filtered = filtered.filter(p => p.year && p.year > yearValue);
          } else if (filter.operator === '<') {
            filtered = filtered.filter(p => p.year && p.year < yearValue);
          }
        }
      } else if (filter.field === 'venue') {
        const venueTerm = filter.value.toLowerCase();
        if (filter.operator === 'includes') {
          filtered = filtered.filter(p =>
            p.venue && p.venue.toLowerCase().includes(venueTerm)
          );
        } else if (filter.operator === 'equals') {
          filtered = filtered.filter(p =>
            p.venue && p.venue.toLowerCase() === venueTerm
          );
        }
      }
    });

    // Apply stats panel filters
    if (selectedYears.length > 0) {
      filtered = filtered.filter(p => selectedYears.includes(p.year));
    }

    if (selectedTopics.length > 0) {
      filtered = filtered.filter(p =>
        p.fieldsOfStudy && p.fieldsOfStudy.some(field => selectedTopics.includes(field))
      );
    }

    if (selectedTypes.length > 0) {
      filtered = filtered.filter(p => {
        const type = p.publicationTypes && p.publicationTypes.length > 0
          ? p.publicationTypes[0]
          : 'article';
        return selectedTypes.includes(type);
      });
    }

    if (selectedInstitutions.length > 0) {
      filtered = filtered.filter(p =>
        p.institutions && Array.isArray(p.institutions) &&
        p.institutions.some(inst => selectedInstitutions.includes(inst))
      );
    }

    if (selectedSources.length > 0) {
      filtered = filtered.filter(p => {
        const paperSources = p.allSources || [p.source || 'Unknown'];
        return paperSources.some(src => selectedSources.includes(src));
      });
    }

    if (openAccessOnly) {
      filtered = filtered.filter(p => p.isOpenAccess === true);
    }

    if (fullContentOnly) {
      filtered = filtered.filter(p => {
        const hasPdf = p.pdf_url || p.openAccessPdf || (p.url && typeof p.url === 'string' && p.url.toLowerCase().endsWith('.pdf'));
        return Boolean(hasPdf);
      });
    }

    // If no active filters at all, show all papers
    const hasStatsFilters =
      openAccessOnly || fullContentOnly || selectedYears.length > 0 || selectedTopics.length > 0 || selectedTypes.length > 0 || selectedInstitutions.length > 0 || selectedSources.length > 0;
    console.log('Filter result:', {
      hasActiveFilters,
      hasStatsFilters,
      filteredCount: filtered.length,
      allPapersCount: allPapers.length
    });

    let result;
    if (!hasActiveFilters && !hasStatsFilters) {
      console.log('No active filters, showing all papers');
      result = [...allPapers];
    } else {
      console.log('Applying filters, showing', filtered.length, 'filtered papers');
      result = filtered;
    }

    // Apply sorting
    const sortedResult = sortPapers(result, sortOption);
    setPapers(sortedResult);
    setCurrentPage(1); // Reset to first page when filters change
  }, [allPapers, filters, selectedYears, selectedTopics, selectedTypes, selectedInstitutions, selectedSources, openAccessOnly, fullContentOnly, sortOption, sortPapers]);

  useEffect(() => {
    if (!topic) {
      navigate('/');
      return;
    }

    setSearchQuery(topic);
    citationNetworkCache.current = null; // Clear citation cache for new topic

    // Record search in history for autocomplete suggestions
    recordSearch(topic);

    // Don't auto-create title_abstract filter — the APIs already handle relevance.
    // Users can manually add filters from the filter bar if needed.
    setFilters([]);

    // Guard against React StrictMode double-render causing duplicate fetches
    let cancelled = false;
    const doFetch = async () => {
      if (!cancelled) {
        await fetchPapers();
      }
    };
    doFetch();
    return () => { cancelled = true; };
  }, [topic]);

  // Apply filters whenever filters, stats filters, or allPapers change
  useEffect(() => {
    if (allPapers.length > 0) {
      applyFilters();
    } else {
      // If no papers, ensure papers state is empty
      setPapers([]);
    }
  }, [filters, selectedYears, selectedTopics, selectedTypes, selectedInstitutions, selectedSources, openAccessOnly, allPapers, applyFilters]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showSortDropdown && !event.target.closest('.sort-dropdown-container')) {
        setShowSortDropdown(false);
      }
      if (showExportDropdown && !event.target.closest('.export-dropdown-container')) {
        setShowExportDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showSortDropdown, showExportDropdown]);

  const addFilter = () => {
    setFilters([...filters, createFilter('title_abstract', 'includes', '')]);
  };

  const removeFilter = (filterId) => {
    setFilters(filters.filter(f => f.id !== filterId));
  };

  const updateFilter = (filterId, field, operator, value) => {
    setFilters(filters.map(f =>
      f.id === filterId ? { ...f, field, operator, value } : f
    ));
  };



  // Export to Excel function
  const exportToExcel = () => {
    if (papers.length === 0) {
      alert('No papers to export');
      return;
    }

    // Prepare data for Excel - flatten the paper objects
    const excelData = papers.map((paper, index) => ({
      'S.No': index + 1,
      'Title': paper.title || 'N/A',
      'Authors': Array.isArray(paper.authors)
        ? paper.authors.map(a => typeof a === 'string' ? a : a.name || a).join('; ')
        : 'N/A',
      'Year': paper.year || 'N/A',
      'Venue/Journal': paper.venue || 'N/A',
      'Citation Count': paper.citationCount || 0,
      'Reference Count': paper.referenceCount || 0,
      'Abstract': paper.abstract || 'N/A',
      'Fields of Study': Array.isArray(paper.fieldsOfStudy)
        ? paper.fieldsOfStudy.join('; ')
        : 'N/A',
      'Publication Types': Array.isArray(paper.publicationTypes)
        ? paper.publicationTypes.join('; ')
        : 'N/A',
      'DOI': paper.externalIds?.DOI || paper.externalIds?.doi || 'N/A',
      'URL': paper.url || 'N/A',
      'PDF URL': paper.openAccessPdf || 'N/A',
      'Open Access': paper.isOpenAccess ? 'Yes' : 'No',
      'Paper ID': paper.paperId || 'N/A',
      'Source': paper.source || 'N/A'
    }));

    // Create workbook and worksheet
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.json_to_sheet(excelData);

    // Set column widths for better readability
    const columnWidths = [
      { wch: 6 },   // S.No
      { wch: 60 },  // Title
      { wch: 40 },  // Authors
      { wch: 8 },   // Year
      { wch: 30 },  // Venue
      { wch: 12 },  // Citation Count
      { wch: 12 },  // Reference Count
      { wch: 80 },  // Abstract
      { wch: 30 },  // Fields of Study
      { wch: 20 },  // Publication Types
      { wch: 30 },  // DOI
      { wch: 50 },  // URL
      { wch: 50 },  // PDF URL
      { wch: 12 },  // Open Access
      { wch: 25 },  // Paper ID
      { wch: 15 },  // Source
    ];
    worksheet['!cols'] = columnWidths;

    // Add metadata sheet
    const metadataSheet = XLSX.utils.json_to_sheet([
      { 'Property': 'Search Query', 'Value': topic || 'N/A' },
      { 'Property': 'Total Results', 'Value': papers.length },
      { 'Property': 'Export Date', 'Value': new Date().toLocaleString() },
      { 'Property': 'Open Access Papers', 'Value': papers.filter(p => p.isOpenAccess).length },
      { 'Property': 'Average Citations', 'Value': Math.round(papers.reduce((sum, p) => sum + (p.citationCount || 0), 0) / papers.length) || 0 },
      { 'Property': 'Year Range', 'Value': `${Math.min(...papers.filter(p => p.year).map(p => p.year))} - ${Math.max(...papers.filter(p => p.year).map(p => p.year))}` },
      { 'Property': 'Current Sort', 'Value': sortOptions.find(o => o.value === sortOption)?.label || 'Default' },
      { 'Property': 'Active Filters', 'Value': filters.length > 0 ? filters.map(f => `${f.field} ${f.operator} "${f.value}"`).join('; ') : 'None' },
    ]);
    metadataSheet['!cols'] = [{ wch: 20 }, { wch: 60 }];

    // Add sheets to workbook
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Research Papers');
    XLSX.utils.book_append_sheet(workbook, metadataSheet, 'Search Metadata');

    // Generate filename with timestamp
    const timestamp = new Date().toISOString().slice(0, 10);
    const sanitizedTopic = (topic || 'research').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 30);
    const filename = `${sanitizedTopic}_papers_${timestamp}.xlsx`;

    // Export the file
    XLSX.writeFile(workbook, filename);
  };

  // Export to PDF function
  const exportToPDF = () => {
    if (papers.length === 0) {
      alert('No papers to export');
      return;
    }

    // Create PDF document (landscape for more columns)
    const doc = new jsPDF('landscape', 'mm', 'a4');

    // Add title
    const sanitizedTopic = (topic || 'Research Papers').slice(0, 50);
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.text(`Research Papers: ${sanitizedTopic}`, 14, 15);

    // Add metadata
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100);
    doc.text(`Generated: ${new Date().toLocaleString()} | Total: ${papers.length} papers | Open Access: ${papers.filter(p => p.isOpenAccess).length}`, 14, 22);
    doc.setTextColor(0);

    // Prepare table data
    const tableData = papers.map((paper, index) => [
      index + 1,
      (paper.title || 'N/A').slice(0, 80) + ((paper.title?.length > 80) ? '...' : ''),
      Array.isArray(paper.authors)
        ? paper.authors.slice(0, 3).map(a => typeof a === 'string' ? a : a.name || a).join(', ') + (paper.authors.length > 3 ? '...' : '')
        : 'N/A',
      paper.year || 'N/A',
      paper.citationCount || 0,
      paper.isOpenAccess ? 'Yes' : 'No',
      (paper.venue || 'N/A').slice(0, 30) + ((paper.venue?.length > 30) ? '...' : ''),
    ]);

    // Create table
    autoTable(doc, {
      startY: 28,
      head: [['#', 'Title', 'Authors', 'Year', 'Citations', 'Open Access', 'Venue']],
      body: tableData,
      headStyles: {
        fillColor: [0, 0, 0],
        textColor: [255, 255, 255],
        fontStyle: 'bold',
        fontSize: 9,
      },
      bodyStyles: {
        fontSize: 8,
        cellPadding: 2,
      },
      columnStyles: {
        0: { cellWidth: 10 },  // #
        1: { cellWidth: 80 },  // Title
        2: { cellWidth: 50 },  // Authors
        3: { cellWidth: 15 },  // Year
        4: { cellWidth: 18 },  // Citations
        5: { cellWidth: 18 },  // Open Access
        6: { cellWidth: 45 },  // Venue
      },
      alternateRowStyles: {
        fillColor: [245, 245, 245],
      },
      margin: { top: 28 },
      didDrawPage: (data) => {
        // Add page number footer
        const pageCount = doc.getNumberOfPages();
        doc.setFontSize(8);
        doc.setTextColor(150);
        doc.text(
          `Page ${data.pageNumber} of ${pageCount}`,
          doc.internal.pageSize.width / 2,
          doc.internal.pageSize.height - 10,
          { align: 'center' }
        );
      },
    });

    // Generate filename
    const timestamp = new Date().toISOString().slice(0, 10);
    const filenameTopic = (topic || 'research').replace(/[^a-zA-Z0-9]/g, '_').slice(0, 30);
    const filename = `${filenameTopic}_papers_${timestamp}.pdf`;

    // Save the PDF
    doc.save(filename);
  };

  // Pagination
  const totalPages = Math.ceil(papers.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentPapers = papers.slice(startIndex, endIndex);

  return (
    <div className="min-h-screen bg-white">
      {/* YouTube-style top progress bar */}
      {fetchProgress > 0 && (
        <div className="fixed top-0 left-0 right-0 z-[9999] h-[3px] bg-transparent">
          <div
            className="h-full bg-black transition-all duration-300 ease-out"
            style={{ width: `${fetchProgress}%`, boxShadow: '0 0 8px rgba(0,0,0,0.4)' }}
          />
        </div>
      )}
      {/* AI backend status banner - search works without AI, summaries/chat/drafts do not */}
      {aiDown && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-3 text-sm text-amber-900">
          The AI backend is currently unavailable, so summaries, chat and drafts will not work right now.
          Search still works. Please try again later.
        </div>
      )}
      {/* Query Builder / Filter Area */}
      <div className="border-b border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4 flex-wrap">
            {/* Main Search Bar */}
            <div className="flex-1 min-w-[300px]">
              <SearchBar
                onSearch={(newTopic) => navigate(`/results?topic=${encodeURIComponent(newTopic)}`)}
                initialValue={topic || ''}
                size="small"
                placeholder="Search for another topic..."
              />
            </div>

            {/* Save/Open Search Dropdown */}
            <SearchDropdown
              topic={topic}
              searchQuery={searchQuery}
            />

            {/* Filter Toggle / Quick Actions */}
            <div className="flex items-center gap-2">
              <button
                onClick={addFilter}
                className="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium transition-colors"
              >
                <Plus className="w-4 h-4" />
                Add Filter
              </button>
            </div>
          </div>

          {/* Active Filters Row */}
          {filters.length > 0 && (
            <div className="mt-4 flex items-center gap-2 flex-wrap border-t border-gray-100 pt-4">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider mr-2">Advanced Filters:</span>
              {filters.map((filter) => (
                <div key={filter.id} className="flex items-center bg-gray-50 border border-gray-200 rounded-lg p-1.5 shadow-sm">
                  <select
                    value={filter.field}
                    onChange={(e) => updateFilter(filter.id, e.target.value, filter.operator, filter.value)}
                    className="text-xs bg-transparent border-none focus:ring-0 font-medium text-gray-700"
                  >
                    <option value="title_abstract">Title & Abstract</option>
                    <option value="open_access">Access</option>
                    <option value="year">Year</option>
                    <option value="venue">Venue</option>
                  </select>

                  <div className="h-4 w-px bg-gray-300 mx-2" />

                  <select
                    value={filter.operator}
                    onChange={(e) => updateFilter(filter.id, filter.field, e.target.value, filter.value)}
                    className="text-xs bg-transparent border-none focus:ring-0 text-gray-600"
                  >
                    {filter.field === 'open_access' ? (
                      <option value="is">is</option>
                    ) : filter.field === 'year' ? (
                      <>
                        <option value="is">is</option>
                        <option value=">">greater than</option>
                        <option value="<">less than</option>
                      </>
                    ) : (
                      <>
                        <option value="includes">includes</option>
                        <option value="equals">equals</option>
                      </>
                    )}
                  </select>

                  <div className="h-4 w-px bg-gray-300 mx-2" />

                  {filter.field === 'open_access' ? (
                    <input
                      type="text"
                      value={filter.value}
                      onChange={(e) => updateFilter(filter.id, filter.field, filter.operator, e.target.value)}
                      className="text-xs bg-transparent border-none focus:ring-0 w-24 placeholder-gray-400"
                      placeholder="e.g. true"
                    />
                  ) : (
                    <input
                      type={filter.field === 'year' ? 'number' : 'text'}
                      value={filter.value}
                      onChange={(e) => updateFilter(filter.id, filter.field, filter.operator, e.target.value)}
                      className="text-xs bg-transparent border-none focus:ring-0 min-w-[120px] placeholder-gray-400"
                      placeholder="Value..."
                    />
                  )}

                  <button
                    onClick={() => removeFilter(filter.id)}
                    className="ml-1 p-1 hover:bg-gray-200 rounded-md transition-colors"
                  >
                    <X className="w-3.5 h-3.5 text-gray-500" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex">
        {/* Left Column - Works List */}
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="max-w-4xl mx-auto">
            {/* Works Header */}
            <div className="border-b border-gray-200 p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-semibold text-black">Works</h2>
                {fromCache && (
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 text-xs font-medium rounded-full border border-yellow-200">
                      Cached
                    </span>
                    <button
                      onClick={() => fetchPapers(true)}
                      className="px-2.5 py-1 text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-md transition-colors font-medium"
                      title="Bypass cache and fetch fresh results from all APIs"
                    >
                      ↻ Refresh
                    </button>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {papers.length > 0 && (
                  <>
                    {/* Sliding Toggle: All Results ↔ Full Access */}
                    <div
                      onClick={() => setFullContentOnly(!fullContentOnly)}
                      className="relative flex items-center bg-gray-200 rounded-full cursor-pointer select-none h-8 w-[200px] border border-gray-300 transition-colors duration-300"
                      title={fullContentOnly ? 'Showing only papers with accessible full content' : 'Showing all results'}
                    >
                      {/* Sliding knob */}
                      <div
                        className={`absolute top-[2px] h-[28px] w-[98px] rounded-full bg-black shadow-md transition-all duration-300 ease-in-out ${fullContentOnly ? 'left-[100px]' : 'left-[2px]'
                          }`}
                      />
                      {/* Left label */}
                      <span className={`relative z-10 flex-1 text-center text-xs font-semibold transition-colors duration-300 ${!fullContentOnly ? 'text-white' : 'text-gray-500'
                        }`}>
                        All Results
                      </span>
                      {/* Right label */}
                      <span className={`relative z-10 flex-1 text-center text-xs font-semibold transition-colors duration-300 ${fullContentOnly ? 'text-white' : 'text-gray-500'
                        }`}>
                        Full Access
                      </span>
                    </div>
                    <button
                      onClick={() => setShowCitationMesh(true)}
                      className="px-3 py-1.5 bg-black text-white rounded text-sm hover:bg-gray-800 transition-colors flex items-center gap-2"
                      title="View Citation Network"
                    >
                      <Network className="w-4 h-4" />
                      Citation Mesh
                    </button>
                  </>
                )}
                {/* Sort Dropdown */}
                <div className="relative sort-dropdown-container">
                  <button
                    onClick={() => setShowSortDropdown(!showSortDropdown)}
                    className={`p-1.5 hover:bg-gray-100 rounded flex items-center gap-1 ${showSortDropdown ? 'bg-gray-100' : ''}`}
                    title="Sort results"
                  >
                    <ArrowUpDown className="w-4 h-4 text-gray-600" />
                    <ChevronDown className={`w-3 h-3 text-gray-600 transition-transform ${showSortDropdown ? 'rotate-180' : ''}`} />
                  </button>

                  {/* Dropdown Menu */}
                  {showSortDropdown && (
                    <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
                      <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase border-b border-gray-100">
                        Sort by
                      </div>
                      {sortOptions.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => {
                            setSortOption(option.value);
                            setShowSortDropdown(false);
                          }}
                          className={`w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center justify-between ${sortOption === option.value ? 'bg-gray-50 text-black font-medium' : 'text-gray-700'
                            }`}
                        >
                          <span>{option.label}</span>
                          {sortOption === option.value && (
                            <Check className="w-4 h-4 text-black" />
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Export Dropdown */}
                <div className="relative export-dropdown-container">
                  <button
                    onClick={() => setShowExportDropdown(!showExportDropdown)}
                    className={`p-1.5 hover:bg-gray-100 rounded flex items-center gap-1 ${showExportDropdown ? 'bg-gray-100' : ''}`}
                    title="Export results"
                  >
                    <Download className="w-4 h-4 text-gray-600" />
                    <ChevronDown className={`w-3 h-3 text-gray-600 transition-transform ${showExportDropdown ? 'rotate-180' : ''}`} />
                  </button>

                  {/* Export Dropdown Menu */}
                  {showExportDropdown && (
                    <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
                      <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase border-b border-gray-100">
                        Export as
                      </div>
                      <button
                        onClick={() => {
                          exportToPDF();
                          setShowExportDropdown(false);
                        }}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 text-gray-700"
                      >
                        <FileText className="w-4 h-4" />
                        Download PDF
                      </button>
                      <button
                        onClick={() => {
                          exportToExcel();
                          setShowExportDropdown(false);
                        }}
                        className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center gap-2 text-gray-700"
                      >
                        <BarChart3 className="w-4 h-4" />
                        Export to Excel
                      </button>
                    </div>
                  )}
                </div>
                <button className="p-1.5 hover:bg-gray-100 rounded">
                  <MoreVertical className="w-4 h-4 text-gray-600" />
                </button>
              </div>
            </div>

            {/* Loading State */}
            {loading && (
              <div className="flex flex-col items-center justify-center py-20">
                <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-black mb-4"></div>
                <p className="text-black text-lg">Searching research papers...</p>
                <p className="text-gray-600 text-sm mt-2">This may take a few moments</p>
              </div>
            )}

            {/* Error State */}
            {error && !loading && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center m-4">
                <p className="text-red-700 text-lg mb-4">{error}</p>
                <button
                  onClick={fetchPapers}
                  className="px-6 py-2 bg-black text-white rounded hover:bg-gray-800 transition-colors"
                >
                  Try Again
                </button>
              </div>
            )}

            {/* Results List */}
            {!loading && !error && papers.length > 0 && (
              <>
                <div className="border-b border-gray-200">
                  {currentPapers.map((paper, index) => {
                    const paperId = paper.arxiv_id || paper.paperId || `${index}-${paper.title}`;
                    return (
                      <PaperListItem
                        key={paperId}
                        paper={paper}
                        isSelected={selectedPaper && (selectedPaper.arxiv_id || selectedPaper.paperId) === paperId}
                        onClick={() => setSelectedPaper(paper)}
                      />
                    );
                  })}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="p-4 flex items-center justify-center gap-2">
                    <button
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1}
                      className="px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      ←
                    </button>
                    {Array.from({ length: Math.min(10, totalPages) }, (_, i) => i + 1).map(page => (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`px-3 py-1.5 border rounded ${currentPage === page
                          ? 'bg-black text-white border-black'
                          : 'border-gray-300 hover:bg-gray-50'
                          }`}
                      >
                        {page}
                      </button>
                    ))}
                    {totalPages > 10 && <span className="px-2 text-gray-500">...</span>}
                    <button
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1.5 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      →
                    </button>
                  </div>
                )}
              </>
            )}

            {/* No Results */}
            {!loading && !error && papers.length === 0 && (
              <div className="text-center py-20">
                <BookOpen className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-600 text-lg">
                  No papers found{topic ? ` for "${topic}"` : ''}
                </p>
                <p className="text-gray-500 text-sm mt-2">
                  Try a different search term or check the spelling.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Stats Panel */}
        {showStatsPanel && (
          <StatsPanel
            papers={papers}
            stats={stats}
            onClose={() => setShowStatsPanel(false)}
            selectedYears={selectedYears}
            setSelectedYears={setSelectedYears}
            selectedTopics={selectedTopics}
            setSelectedTopics={setSelectedTopics}
            selectedTypes={selectedTypes}
            setSelectedTypes={setSelectedTypes}
            selectedSources={selectedSources}
            setSelectedSources={setSelectedSources}
            selectedInstitutions={selectedInstitutions}
            setSelectedInstitutions={setSelectedInstitutions}
            openAccessOnly={openAccessOnly}
            onToggleOpenAccess={() => setOpenAccessOnly(!openAccessOnly)}
            searchQuery={topic}
            onRelatedSearch={(query) => navigate(`/results?topic=${encodeURIComponent(query)}`)}
            relatedSearches={relatedSearches}
            relatedLoading={relatedLoading}
          />
        )}

        {/* Detail Panel Overlay */}
        {selectedPaper && (
          <>
            <DetailPanel
              paper={selectedPaper}
              onClose={() => setSelectedPaper(null)}
              summaryJobs={summaryJobs}
              onStartSummarize={startBackgroundSummarize}
              isSplitScreen={showCitationMesh && !!selectedPaper}
              unpaywallPdfUrl={unpaywallPdfUrl}
            />
            <div
              className="fixed inset-0 bg-black/30 z-40 md:hidden"
              onClick={() => setSelectedPaper(null)}
            ></div>
          </>
        )}

        {/* Citation Mesh Overlay */}
        {showCitationMesh && (
          <CitationMesh
            papers={allPapers}
            cachedNetwork={citationNetworkCache.current}
            onNetworkBuilt={(data) => { citationNetworkCache.current = data; }}
            onClose={() => setShowCitationMesh(false)}
            isSplitScreen={showCitationMesh && !!selectedPaper}
            onNodeClick={(nodeData) => {
              // Find the paper in allPapers and show its details
              const paper = allPapers.find(p =>
                (p.paperId || p.id) === nodeData.paperId
              );
              if (paper) {
                setSelectedPaper(paper);
              }
            }}
          />
        )}
      </div>

      {/* Floating Bubbles for background summarization jobs */}
      {summaryJobs.size > 0 && (
        <FloatingBubbles
          summaryJobs={summaryJobs}
          onBubbleClick={handleBubbleClick}
          onDismiss={handleBubbleDismiss}
        />
      )}

      {/* Results-level Toast Container for background job notifications */}
      <ToastContainer toasts={resultToasts} removeToast={removeResultToast} />
    </div>
  );
}

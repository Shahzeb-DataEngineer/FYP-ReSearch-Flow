/**
 * useSearchHistory Hook
 * 
 * Manages search history for the logged-in user using Supabase.
 * Provides:
 *  - Recording new searches
 *  - Fetching past searches for autocomplete suggestions
 *  - Deleting search history entries
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { supabase } from '../lib/supabase';
import { useAuth } from './useAuth';

// Common academic research topic suggestions for non-logged-in users
// or users with no search history
const DEFAULT_SUGGESTIONS = [
    'machine learning healthcare',
    'deep learning image classification',
    'natural language processing sentiment analysis',
    'reinforcement learning robotics',
    'computer vision object detection',
    'transformer models text generation',
    'federated learning privacy',
    'graph neural networks drug discovery',
    'generative adversarial networks image synthesis',
    'attention mechanism neural networks',
    'transfer learning medical imaging',
    'quantum computing optimization',
    'blockchain decentralized finance',
    'explainable artificial intelligence',
    'autonomous vehicles perception',
    'climate change prediction models',
    'protein structure prediction',
    'speech recognition deep learning',
    'recommendation systems collaborative filtering',
    'cybersecurity intrusion detection',
    'cricket performance analysis',
    'cricket ball tracking technology',
    'biomechanics of cricket bowling',
    'statistical analysis in sports',
    'smart cities IoT sensors',
    'renewable energy storage systems',
    'CRISPR gene editing applications',
    'nanotechnology in drug delivery',
    'cyber-physical systems security',
    'autonomous underwater vehicles',
    'human-computer interaction AR/VR',
    'edge computing latency optimization',
    'digital twins in manufacturing',
    'personalized medicine genomics',
    'sustainable agriculture technology',
];

export function useSearchHistory() {
    const { user, isAuthenticated } = useAuth();
    const [searchHistory, setSearchHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [trendingTopics, setTrendingTopics] = useState([]);
    const [trendingLoading, setTrendingLoading] = useState(false);
    const trendingCacheRef = useRef({ data: null, timestamp: 0 });
    const TRENDING_CACHE_MS = 10 * 60 * 1000; // 10-minute cache

    // Fetch user's search history from Supabase
    const fetchSearchHistory = useCallback(async () => {
        if (!isAuthenticated || !user) {
            setSearchHistory([]);
            return;
        }

        setLoading(true);
        try {
            const { data, error } = await supabase
                .from('search_history')
                .select('id, query, searched_at')
                .eq('user_id', user.id)
                .order('searched_at', { ascending: false })
                .limit(50);

            if (error) {
                // Table might not exist yet — that's fine, we'll create it on first insert
                console.warn('Could not fetch search history:', error.message);
                setSearchHistory([]);
            } else {
                // Deduplicate by query (keep most recent)
                const seen = new Set();
                const unique = (data || []).filter(entry => {
                    const q = entry.query.toLowerCase().trim();
                    if (seen.has(q)) return false;
                    seen.add(q);
                    return true;
                });
                setSearchHistory(unique);
            }
        } catch (err) {
            console.warn('Search history fetch error:', err);
            setSearchHistory([]);
        } finally {
            setLoading(false);
        }
    }, [user, isAuthenticated]);

    // Load search history on mount / auth change
    useEffect(() => {
        fetchSearchHistory();
    }, [fetchSearchHistory]);

    // Record a new search query
    const recordSearch = useCallback(async (query) => {
        if (!isAuthenticated || !user || !query?.trim()) return;

        const trimmedQuery = query.trim();

        try {
            // Upsert: if same query exists, update the timestamp
            const { error } = await supabase
                .from('search_history')
                .upsert(
                    {
                        user_id: user.id,
                        query: trimmedQuery,
                        searched_at: new Date().toISOString(),
                    },
                    {
                        onConflict: 'user_id,query',
                    }
                );

            if (error) {
                // If table doesn't exist, try to create it
                if (error.code === '42P01' || error.message?.includes('does not exist')) {
                    console.warn('search_history table does not exist. Please create it in Supabase.');
                } else {
                    console.warn('Could not record search:', error.message);
                }
            } else {
                // Refresh history after recording
                fetchSearchHistory();
            }
        } catch (err) {
            console.warn('Search recording error:', err);
        }
    }, [user, isAuthenticated, fetchSearchHistory]);

    // Delete a single history entry
    const deleteHistoryEntry = useCallback(async (entryId) => {
        if (!isAuthenticated || !user) return;

        try {
            await supabase
                .from('search_history')
                .delete()
                .eq('id', entryId)
                .eq('user_id', user.id);

            setSearchHistory(prev => prev.filter(entry => entry.id !== entryId));
        } catch (err) {
            console.warn('Delete history error:', err);
        }
    }, [user, isAuthenticated]);

    // Clear all search history
    const clearHistory = useCallback(async () => {
        if (!isAuthenticated || !user) return;

        try {
            await supabase
                .from('search_history')
                .delete()
                .eq('user_id', user.id);

            setSearchHistory([]);
        } catch (err) {
            console.warn('Clear history error:', err);
        }
    }, [user, isAuthenticated]);

    /**
     * Fetch trending research topics from OpenAlex (external only).
     * When a query is provided, results are filtered to match that query.
     * When empty, shows global trending topics.
     * Results are cached per query for 10 minutes.
     */
    const fetchTrendingTopics = useCallback(async (query = '') => {
        const trimmed = (query || '').trim().toLowerCase();
        const cacheKey = trimmed || '__global__';

        // Return cache if still valid for this query
        const now = Date.now();
        const cached = trendingCacheRef.current;
        if (cached.key === cacheKey && cached.data && (now - cached.timestamp) < TRENDING_CACHE_MS) {
            setTrendingTopics(cached.data);
            return cached.data;
        }

        setTrendingLoading(true);
        try {
            // Calculate date 30 days ago for "recent" filter
            const thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
            const dateStr = thirtyDaysAgo.toISOString().split('T')[0];

            // Build URLs based on whether we have a query
            const topicsUrl = trimmed.length >= 2
                ? `https://api.openalex.org/autocomplete/topics?q=${encodeURIComponent(trimmed)}`
                : 'https://api.openalex.org/topics?sort=works_count:desc&per-page=8&select=display_name,description,works_count';

            const worksFilter = trimmed.length >= 2
                ? `https://api.openalex.org/works?search=${encodeURIComponent(trimmed)}&filter=from_publication_date:${dateStr}&sort=cited_by_count:desc&per-page=8&select=display_name,cited_by_count`
                : `https://api.openalex.org/works?filter=from_publication_date:${dateStr}&sort=cited_by_count:desc&per-page=8&select=display_name,cited_by_count,topics`;

            // Fetch both endpoints in parallel
            const [topicsRes, hotPapersRes] = await Promise.allSettled([
                fetch(topicsUrl),
                fetch(worksFilter)
            ]);

            const trending = [];

            // Parse trending topics
            if (topicsRes.status === 'fulfilled' && topicsRes.value.ok) {
                const topicsData = await topicsRes.value.json();
                const topicsList = topicsData.results || [];
                const topics = topicsList.slice(0, 8).map(t => ({
                    text: t.display_name,
                    type: 'trending_topic',
                    hint: t.works_count ? `${Number(t.works_count).toLocaleString()} papers` : (t.hint || ''),
                    description: t.description || '',
                }));
                trending.push(...topics);
            }

            // Parse hot papers (most-cited recent papers)
            if (hotPapersRes.status === 'fulfilled' && hotPapersRes.value.ok) {
                const papersData = await hotPapersRes.value.json();
                const seen = new Set(trending.map(t => t.text.toLowerCase()));
                const hotPapers = (papersData.results || [])
                    .filter(p => p.display_name && !seen.has(p.display_name.toLowerCase()))
                    .slice(0, 6)
                    .map(p => ({
                        text: p.display_name,
                        type: 'hot_paper',
                        hint: `${(p.cited_by_count || 0).toLocaleString()} citations`,
                    }));
                trending.push(...hotPapers);
            }

            // Cache results keyed by query
            trendingCacheRef.current = { key: cacheKey, data: trending, timestamp: now };
            setTrendingTopics(trending);
            return trending;
        } catch (err) {
            console.warn('Trending topics fetch error:', err);
            return [];
        } finally {
            setTrendingLoading(false);
        }
    }, [TRENDING_CACHE_MS]);

    /**
     * Fetch external autocomplete suggestions from OpenAlex
     */
    const fetchExternalAutocomplete = async (input) => {
        if (!input || input.trim().length < 3) return [];

        try {
            // Fetch from OpenAlex autocomplete API
            // Searching for 'works' gives us actual paper titles/topics
            const response = await fetch(`https://api.openalex.org/autocomplete/works?q=${encodeURIComponent(input)}`);
            if (!response.ok) return [];

            const data = await response.json();

            // Format results and filter out computer source code scripts (.py, .js, etc.)
            // OpenAlex sometimes indexes code repositories as 'works', which clutters suggestions.
            return (data.results || [])
                .filter(item => {
                    const name = (item.display_name || '').toLowerCase();
                    // Exclude common code extensions and patterns like file_name.py
                    const isCodeFile = /\.(?:py|js|cpp|c|h|java|cs|php|rb|go|rs|sh|pyc)$/.test(name) ||
                        (name.includes('_') && name.endsWith('.py'));
                    return !isCodeFile;
                })
                .map(item => ({
                    text: item.display_name,
                    type: 'suggestion',
                    hint: item.hint // e.g., "Work", "Concept"
                }));
        } catch (err) {
            console.warn('Autocomplete API error:', err);
            return [];
        }
    };

    /**
     * Get autocomplete suggestions based on the current input.
     * Combines:
     *  1. User's search history (instant local)
     *  2. OpenAlex external autocomplete (async)
     *  3. Static default suggestions (fallback/empty state)
     */
    const getSuggestions = useCallback(async (input, maxResults = 8) => {
        const query = (input || '').toLowerCase().trim();

        const suggestions = [];
        const seen = new Set();

        // CASE 1: Empty input - show history or top defaults
        if (query.length === 0) {
            // Priority 1: User History
            if (isAuthenticated && searchHistory.length > 0) {
                return searchHistory.slice(0, 6).map(entry => ({
                    text: entry.query,
                    type: 'history',
                    id: entry.id,
                }));
            }
            // Priority 2: Top Default Suggestions
            return DEFAULT_SUGGESTIONS.slice(0, 6).map(topic => ({
                text: topic,
                type: 'suggestion',
            }));
        }

        // CASE 2: Search input provided

        // 1. Match from user's search history (instant local)
        for (const entry of searchHistory) {
            if (suggestions.length >= 3) break; // Keep some space for other types
            const entryLower = entry.query.toLowerCase();
            if (entryLower.includes(query) && !seen.has(entryLower)) {
                seen.add(entryLower);
                suggestions.push({
                    text: entry.query,
                    type: 'history',
                    id: entry.id,
                });
            }
        }

        // 2. Match from local DEFAULT_SUGGESTIONS (instant fallback)
        for (const topic of DEFAULT_SUGGESTIONS) {
            if (suggestions.length >= 6) break; // Don't fill it entirely yet
            const topicLower = topic.toLowerCase();
            if (topicLower.includes(query) && !seen.has(topicLower)) {
                seen.add(topicLower);
                suggestions.push({
                    text: topic,
                    type: 'suggestion',
                });
            }
        }

        // 3. Fetch from OpenAlex (external async) - only if query is long enough
        if (query.length >= 3) {
            // We do this last to ensure something is shown immediately from local lists
            const external = await fetchExternalAutocomplete(query);
            for (const item of external) {
                if (suggestions.length >= maxResults) break;
                const lower = item.text.toLowerCase();
                if (!seen.has(lower)) {
                    seen.add(lower);
                    suggestions.push(item);
                }
            }
        }

        // If we still have space, fill it up with more defaults that don't necessarily match (last resort)
        if (suggestions.length < 3) {
            for (const topic of DEFAULT_SUGGESTIONS) {
                if (suggestions.length >= 5) break;
                if (!seen.has(topic.toLowerCase())) {
                    suggestions.push({ text: topic, type: 'suggestion' });
                    seen.add(topic.toLowerCase());
                }
            }
        }

        return suggestions;
    }, [searchHistory, isAuthenticated]);

    return {
        searchHistory,
        loading,
        recordSearch,
        deleteHistoryEntry,
        clearHistory,
        getSuggestions,
        fetchSearchHistory,
        trendingTopics,
        trendingLoading,
        fetchTrendingTopics,
    };
}

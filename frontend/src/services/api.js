import { supabase } from '../lib/supabase';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

/**
 * Authorization header for the authenticated backend routes
 * (chat and draft generation). Search and summarization stay
 * public; chat and drafts require a logged-in user, so the
 * Supabase session access token is sent as a Bearer token.
 * Returns {} when there is no session, letting the backend
 * answer 401 with a clear "log in" message.
 */
async function getAuthHeaders() {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data?.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

/**
 * Ask the backend whether the local AI model is reachable.
 * Used for the "AI unavailable" banner instead of letting
 * summarize / chat / draft hang or fail silently.
 */
export async function checkAiReady() {
  try {
    const base = API_BASE_URL.replace(/\/api\/v1$/, '');
    const response = await fetch(`${base}/ready`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!response.ok) return false;
    const data = await response.json();
    return data.ollama === true;
  } catch {
    return false;
  }
}

class APIError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.details = details;
  }
}

export const searchAPI = {
  /**
   * Fetch research papers for a given topic
   * @param {string} topic - Research topic to search
   * @param {number} limit - Number of papers to fetch (default: 20)
   * @param {boolean} extractContent - Whether to extract PDF content (default: false)
   * @returns {Promise<Object>} Response with papers array
   */
  async fetchPapers(topic, limit = 20, extractContent = false) {
    try {
      const url = new URL(`${API_BASE_URL}/search/fetch`);
      url.searchParams.append('topic', topic);
      url.searchParams.append('limit', limit);
      url.searchParams.append('extract_content', extractContent);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to fetch papers',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      // Network or other errors
      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Get stored papers from database
   * @param {string} topic - Filter by topic (optional)
   * @param {number} limit - Number of papers to retrieve
   * @param {number} offset - Pagination offset
   */
  async getStoredPapers(topic = null, limit = 50, offset = 0) {
    try {
      const url = new URL(`${API_BASE_URL}/papers`);
      if (topic) url.searchParams.append('topic', topic);
      url.searchParams.append('limit', limit);
      url.searchParams.append('offset', offset);

      const response = await fetch(url.toString());
      const data = await response.json();

      if (!response.ok) {
        throw new APIError('Failed to retrieve papers', response.status, data);
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error', 0, { originalError: error.message });
    }
  },

  /**
   * Get all unique topics
   */
  async getTopics() {
    try {
      const response = await fetch(`${API_BASE_URL}/papers/topics/all`);
      const data = await response.json();

      if (!response.ok) {
        throw new APIError('Failed to retrieve topics', response.status, data);
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error', 0, { originalError: error.message });
    }
  },

  /**
   * Get citation network for papers
   * @param {Array} papers - Array of paper objects
   * @param {number} maxDepth - Maximum depth of citation exploration (default: 1)
   * @param {number} maxNodes - Maximum number of nodes (default: 50)
   * @returns {Promise<Object>} Citation network with nodes and edges
   */
  async getCitationNetwork(papers, maxDepth = 2, maxNodes = 80) {
    try {
      const response = await fetch(`${API_BASE_URL}/citation/network`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          papers: papers,
          max_depth: maxDepth,
          max_nodes: maxNodes,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to build citation network',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error', 0, { originalError: error.message });
    }
  }
};

// Saved Articles API functions
export const savedArticlesAPI = {
  /**
   * Save an article to user's favorites
   * @param {string} paperId - OpenAlex paper ID
   * @param {Object} paperData - Paper data to save
   * @returns {Promise<Object>} Saved article data
   */
  async saveArticle(paperId, paperData) {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        throw new APIError('User not authenticated', 401, { requiresAuth: true });
      }

      const { data, error } = await supabase
        .from('saved_articles')
        .upsert({
          user_id: user.id,
          paper_id: paperId,
          title: paperData.title || 'Untitled Paper',
        }, {
          onConflict: 'user_id,paper_id'
        })
        .select()
        .single();

      if (error) throw error;
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Failed to save article', 0, { originalError: error.message });
    }
  },

  /**
   * Remove an article from user's favorites
   * @param {string} paperId - OpenAlex paper ID
   * @returns {Promise<void>}
   */
  async unsaveArticle(paperId) {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        throw new APIError('User not authenticated', 401, { requiresAuth: true });
      }

      const { error } = await supabase
        .from('saved_articles')
        .delete()
        .eq('user_id', user.id)
        .eq('paper_id', paperId);

      if (error) throw error;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Failed to unsave article', 0, { originalError: error.message });
    }
  },

  /**
   * Get saved article with notes
   * @param {string} paperId - OpenAlex paper ID
   * @returns {Promise<Object|null>} Saved article data or null if not saved
   */
  async getSavedArticle(paperId) {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        return null;
      }

      const { data, error } = await supabase
        .from('saved_articles')
        .select('*')
        .eq('user_id', user.id)
        .eq('paper_id', paperId)
        .single();

      if (error) {
        if (error.code === 'PGRST116') {
          // No rows returned
          return null;
        }
        throw error;
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      // Return null on error to gracefully handle unauthenticated users
      return null;
    }
  },

  /**
   * Update notes for a saved article
   * @param {string} paperId - OpenAlex paper ID
   * @param {string} notes - Notes text
   * @returns {Promise<Object>} Updated article data
   */
  async updateArticleNotes(paperId, notes) {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        throw new APIError('User not authenticated', 401, { requiresAuth: true });
      }

      const { data, error } = await supabase
        .from('saved_articles')
        .update({ notes: notes || null })
        .eq('user_id', user.id)
        .eq('paper_id', paperId)
        .select()
        .single();

      if (error) throw error;
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Failed to update notes', 0, { originalError: error.message });
    }
  },

  /**
   * Get all saved articles for current user
   * @returns {Promise<Array>} Array of saved articles
   */
  async getUserSavedArticles() {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) {
        return [];
      }

      const { data, error } = await supabase
        .from('saved_articles')
        .select('*')
        .eq('user_id', user.id)
        .order('updated_at', { ascending: false });

      if (error) throw error;
      return data || [];
    } catch (error) {
      if (error instanceof APIError) throw error;
      return [];
    }
  }
};

// arXiv API functions
export const arxivAPI = {
  /**
   * Search arXiv for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/arxiv/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search arXiv',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from arXiv
   * @param {string} arxivId - arXiv ID (e.g., "1234.5678") OR pdfUrl
   * @param {string} pdfUrl - Optional PDF URL (alternative to arxivId)
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(arxivId = null, pdfUrl = null) {
    try {
      const requestBody = {};
      if (arxivId) {
        requestBody.arxiv_id = arxivId;
      } else if (pdfUrl) {
        requestBody.pdf_url = pdfUrl;
      } else {
        throw new APIError('Either arxivId or pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/arxiv/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper from arXiv
   * @param {string} arxivId - arXiv ID (e.g., "1234.5678") OR pdfUrl
   * @param {string} pdfUrl - Optional PDF URL (alternative to arxivId)
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(arxivId = null, pdfUrl = null, title = "", abstract = "") {
    try {
      const requestBody = { title, abstract };
      if (arxivId) {
        requestBody.arxiv_id = arxivId;
      } else if (pdfUrl) {
        requestBody.pdf_url = pdfUrl;
      } else {
        throw new APIError('Either arxivId or pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/arxiv/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper
   * @param {string} arxivId - arXiv ID OR null
   * @param {string} pdfUrl - PDF URL OR null
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional conversation history
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(arxivId = null, pdfUrl = null, question = "", conversationHistory = [], pdfText = null) {
    try {
      const requestBody = {};
      if (arxivId) requestBody.arxiv_id = arxivId;
      else if (pdfUrl) requestBody.pdf_url = pdfUrl;
      else if (!pdfText) throw new APIError('Either arxivId, pdfUrl, or pdfText must be provided', 400);

      requestBody.question = question;
      // Pass pre-extracted text to skip backend PDF download
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/arxiv/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};

// CORE API functions
export const coreAPI = {
  /**
   * Search CORE for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/core/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search CORE',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from CORE paper
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/core/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper from CORE
   * @param {string} pdfUrl - PDF URL
   * @param {string} title - Optional title
   * @param {string} abstract - Optional abstract
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "") {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/core/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          pdf_url: pdfUrl,
          title: title,
          abstract: abstract 
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a CORE paper
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/core/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};

// PubMed Central (PMC) API functions
export const pmcAPI = {
  /**
   * Search PMC for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/pmc/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search PMC',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from PMC paper
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/pmc/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper from PMC
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, pmcId = null, title = "", abstract = "") {
    try {
      if (!pdfUrl && !pmcId) {
        throw new APIError('pdfUrl or pmcId must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/pmc/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          pdf_url: pdfUrl,
          pmc_id: pmcId,
          title: title,
          abstract: abstract
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a PMC paper
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/pmc/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};

// Semantic Scholar API functions
export const semanticScholarAPI = {
  /**
   * Search Semantic Scholar for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/semantic-scholar/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search Semantic Scholar',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from any paper (works with any source)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/semantic-scholar/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper from any source (works with any PDF URL)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "") {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/semantic-scholar/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          pdf_url: pdfUrl,
          title: title,
          abstract: abstract 
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper from any source
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/semantic-scholar/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};

// Crossref API functions (free source, no API key)
export const crossrefAPI = {
  /**
   * Search Crossref for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/crossref/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search Crossref',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from any paper (works with any source)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/crossref/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper (works with a PDF URL or, as a fallback, the
   * paper's abstract - the Crossref backend supports both)
   * @param {string} pdfUrl - PDF URL
   * @param {string} title - Paper title
   * @param {string} abstract - Paper abstract (used when no PDF is available)
   * @param {string} doi - Paper DOI (optional)
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "", doi = "") {
    try {
      if (!pdfUrl && !abstract) {
        throw new APIError('pdfUrl or abstract must be provided', 400);
      }

      const body = {
        pdf_url: pdfUrl,
        title: title,
        abstract: abstract
      };
      if (doi) body.doi = doi;

      const response = await fetch(`${API_BASE_URL}/crossref/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper from any source
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/crossref/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};

// Europe PMC API functions (free source, no API key)
export const europePmcAPI = {
  /**
   * Search Europe PMC for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/europe-pmc/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search Europe PMC',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from any paper (works with any source)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/europe-pmc/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper (works with a PDF URL or, as a fallback, the
   * paper's abstract - the Europe PMC backend supports both)
   * @param {string} pdfUrl - PDF URL
   * @param {string} title - Paper title
   * @param {string} abstract - Paper abstract (used when no PDF is available)
   * @param {string} doi - Paper DOI (optional)
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "", doi = "") {
    try {
      if (!pdfUrl && !abstract) {
        throw new APIError('pdfUrl or abstract must be provided', 400);
      }

      const body = {
        pdf_url: pdfUrl,
        title: title,
        abstract: abstract
      };
      if (doi) body.doi = doi;

      const response = await fetch(`${API_BASE_URL}/europe-pmc/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper from any source
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/europe-pmc/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};

// PubMed API functions (free source, no API key)
export const pubmedAPI = {
  /**
   * Search PubMed for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/pubmed/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search PubMed',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from any paper (works with any source)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/pubmed/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper (works with a PDF URL or, as a fallback, the
   * paper's abstract - the PubMed backend supports both)
   * @param {string} pdfUrl - PDF URL
   * @param {string} title - Paper title
   * @param {string} abstract - Paper abstract (used when no PDF is available)
   * @param {string} doi - Paper DOI (optional)
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "", doi = "") {
    try {
      if (!pdfUrl && !abstract) {
        throw new APIError('pdfUrl or abstract must be provided', 400);
      }

      const body = {
        pdf_url: pdfUrl,
        title: title,
        abstract: abstract
      };
      if (doi) body.doi = doi;

      const response = await fetch(`${API_BASE_URL}/pubmed/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper from any source
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/pubmed/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};


// DOAJ API functions (free source, no API key)
export const doajAPI = {
  /**
   * Search DOAJ for papers
   * @param {string} query - Search query/topic
   * @param {number} limit - Number of results (default: 20)
   * @returns {Promise<Object>} Response with papers array
   */
  async searchPapers(query, limit = 20) {
    try {
      const url = new URL(`${API_BASE_URL}/doaj/search`);
      url.searchParams.append('query', query);
      url.searchParams.append('limit', limit);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search DOAJ',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from any paper (works with any source)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/doaj/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper (works with a PDF URL or, as a fallback, the
   * paper's abstract - the DOAJ backend supports both)
   * @param {string} pdfUrl - PDF URL
   * @param {string} title - Paper title
   * @param {string} abstract - Paper abstract (used when no PDF is available)
   * @param {string} doi - Paper DOI (optional)
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "", doi = "") {
    try {
      if (!pdfUrl && !abstract) {
        throw new APIError('pdfUrl or abstract must be provided', 400);
      }

      const body = {
        pdf_url: pdfUrl,
        title: title,
        abstract: abstract
      };
      if (doi) body.doi = doi;

      const response = await fetch(`${API_BASE_URL}/doaj/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper from any source
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/doaj/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};


// Unpaywall API functions (free source, no API key)
export const unpaywallAPI = {
  /**
   * Look up a paper by DOI on Unpaywall (DOI-based source, no keyword search)
   * @param {string} doi - DOI of the paper, with or without a doi.org prefix
   * @returns {Promise<Object>} Response with a single paper array, or no_results
   *   when the DOI has no open-access copy
   */
  async searchPapers(doi) {
    try {
      const url = new URL(`${API_BASE_URL}/unpaywall/search`);
      url.searchParams.append('doi', doi);

      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to search Unpaywall',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Extract full PDF content from any paper (works with any source)
   * @param {string} pdfUrl - PDF URL
   * @returns {Promise<Object>} Full extracted text from PDF
   */
  async extractPdfContent(pdfUrl) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const response = await fetch(`${API_BASE_URL}/unpaywall/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pdf_url: pdfUrl }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to extract PDF content',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Summarize a paper (works with a PDF URL or, as a fallback, the
   * paper's abstract - the Unpaywall backend supports both)
   * @param {string} pdfUrl - PDF URL
   * @param {string} title - Paper title
   * @param {string} abstract - Paper abstract (used when no PDF is available)
   * @param {string} doi - Paper DOI (optional)
   * @returns {Promise<Object>} Summary with structured sections
   */
  async summarizePaper(pdfUrl, title = "", abstract = "", doi = "") {
    try {
      if (!pdfUrl && !abstract) {
        throw new APIError('pdfUrl or abstract must be provided', 400);
      }

      const body = {
        pdf_url: pdfUrl,
        title: title,
        abstract: abstract
      };
      if (doi) body.doi = doi;

      const response = await fetch(`${API_BASE_URL}/unpaywall/summarize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new APIError(
          data.detail?.message || 'Failed to summarize paper',
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        'Network error: Could not connect to server',
        0,
        { originalError: error.message }
      );
    }
  },

  /**
   * Ask a question about a paper from any source
   * @param {string} pdfUrl - PDF URL
   * @param {string} question - Question to ask
   * @param {Array} conversationHistory - Optional
   * @param {string} pdfText - Optional pre-extracted text (skips backend PDF extraction)
   */
  async askQuestion(pdfUrl, question = "", conversationHistory = [], pdfText = null) {
    try {
      if (!pdfUrl && !pdfText) throw new APIError('pdfUrl or pdfText must be provided', 400);

      const requestBody = { question };
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (pdfText && pdfText.length > 100) requestBody.pdf_text = pdfText;
      if (conversationHistory && conversationHistory.length > 0) {
        requestBody.conversation_history = conversationHistory;
      }

      const response = await fetch(`${API_BASE_URL}/unpaywall/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get answer', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  }
};


// Trends API functions
export const trendsAPI = {
  /**
   * Get trending academic research topics/concepts
   * @returns {Promise<Object>} Response with topics array
   */
  getTrendingTopics: async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/trends/topics`);
      if (!response.ok) {
        throw new APIError('Failed to fetch trending topics', response.status);
      }
      return await response.json();
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError(error.message || 'Failed to fetch trending topics');
    }
  }
};

// Draft Generation API functions
export const draftAPI = {
  /**
   * Generate a structured research draft from a paper's PDF
   * @param {string} pdfUrl - Open-access PDF URL
   * @param {Object} metadata - Optional paper metadata { title, authors, abstract }
   * @returns {Promise<Object>} Response with draft sections and figure analyses
   */
  async generateDraft(pdfUrl, metadata = {}) {
    try {
      if (!pdfUrl) {
        throw new APIError('pdfUrl must be provided', 400);
      }

      const requestBody = {
        pdf_url: pdfUrl,
        title: metadata.title || '',
        authors: metadata.authors || '',
        abstract: metadata.abstract || '',
      };

      const response = await fetch(`${API_BASE_URL}/draft/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(await getAuthHeaders()),
        },
        body: JSON.stringify(requestBody),
      });

      let data;
      try {
        data = await response.json();
      } catch {
        throw new APIError(
          `Server returned ${response.status} but no valid JSON response.`,
          response.status
        );
      }

      if (!response.ok) {
        if (response.status === 401) {
          throw new APIError(
            'Please log in to generate drafts. Draft generation is available to signed-in researchers.',
            401,
            data.detail
          );
        }
        const errorMsg = data.detail?.message || data.detail || 'Failed to generate draft';
        throw new APIError(
          typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg),
          response.status,
          data.detail
        );
      }

      return data;
    } catch (error) {
      if (error instanceof APIError) {
        throw error;
      }

      throw new APIError(
        `Network/Parsing error: ${error.message || 'Could not connect to server'}`,
        0,
        { originalError: error.message }
      );
    }
  }
};

// Unified Chat API — uses /chat/ask with Redis session persistence
export const chatAPI = {
  /**
   * Ask a question about a paper using RAG (local Ollama + FAISS + BM25).
   * @param {string} question - The question to ask
   * @param {object} options - { pdfText, pdfUrl, abstract, sessionId, paperTitle, paperSource }
   * @returns {Promise<Object>} { status, session_id, question, answer }
   */
  async askQuestion(question, { pdfText, pdfUrl, abstract, sessionId, paperTitle, paperSource } = {}) {
    try {
      const requestBody = { question };
      if (pdfText && pdfText.length > 50) requestBody.pdf_text = pdfText;
      if (pdfUrl) requestBody.pdf_url = pdfUrl;
      if (abstract) requestBody.abstract = abstract;
      if (sessionId) requestBody.session_id = sessionId;
      if (paperTitle) requestBody.paper_title = paperTitle;
      if (paperSource) requestBody.paper_source = paperSource;

      const controller = new AbortController();
      const chatAskTimeoutMs = 600000; // 10 min — first request may index a full PDF + embeddings
      const timeoutId = setTimeout(() => controller.abort(), chatAskTimeoutMs);

      let response;
      try {
        response = await fetch(`${API_BASE_URL}/chat/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(await getAuthHeaders()) },
          body: JSON.stringify(requestBody),
          signal: controller.signal,
        });
      } finally {
        clearTimeout(timeoutId);
      }

      const data = await response.json();
      if (!response.ok) {
        if (response.status === 401) {
          throw new APIError(
            'Please log in to use AI chat. Chat is available to signed-in researchers.',
            401,
            data.detail
          );
        }
        throw new APIError(
          data.detail?.message || data.detail || 'Failed to get answer',
          response.status,
          data.detail
        );
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      if (error?.name === 'AbortError') {
        throw new APIError(
          'Request timed out. The first question can take a while while the paper is indexed; try again or use a shorter paper.',
          0,
          { originalError: 'AbortError' }
        );
      }
      throw new APIError('Network error: Could not connect to server', 0, { originalError: error.message });
    }
  },

  /**
   * Get chat history for a session from Redis.
   * @param {string} sessionId - Session ID
   */
  async getHistory(sessionId) {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/history/${sessionId}`, {
        headers: { ...(await getAuthHeaders()) },
      });
      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to get history', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error', 0, { originalError: error.message });
    }
  },

  /**
   * Clear chat history for a session.
   * @param {string} sessionId - Session ID
   */
  async clearHistory(sessionId) {
    try {
      const response = await fetch(`${API_BASE_URL}/chat/history/${sessionId}`, {
        method: 'DELETE',
        headers: { ...(await getAuthHeaders()) },
      });
      const data = await response.json();
      if (!response.ok) {
        throw new APIError(data.detail?.message || 'Failed to clear history', response.status, data.detail);
      }
      return data;
    } catch (error) {
      if (error instanceof APIError) throw error;
      throw new APIError('Network error', 0, { originalError: error.message });
    }
  }
};

export { APIError };
import React, { useEffect, useState } from 'react';
import { libraryAPI, APIError } from '../services/api';
import { supabase } from '../lib/supabase';

const USER_ID = 'local';

async function currentUserId() {
  try {
    const { data: { user } } = await supabase.auth.getUser();
    return user ? user.id : USER_ID;
  } catch {
    return USER_ID;
  }
}

export default function MyLibrary() {
  const [userId, setUserId] = useState(USER_ID);
  const [papers, setPapers] = useState([]);
  const [topics, setTopics] = useState([]);
  const [graph, setGraph] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [topicInput, setTopicInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const refresh = async (uid) => {
    try {
      const [lib, graphData, alertData] = await Promise.all([
        libraryAPI.getPapers(uid),
        libraryAPI.getGraph(uid),
        libraryAPI.getAlerts(uid),
      ]);
      setPapers(lib.papers || []);
      setTopics(lib.topics || []);
      setGraph(graphData);
      setAlerts(alertData.alerts || []);
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Failed to load library.');
    }
  };

  useEffect(() => {
    let cancelled = false;
    currentUserId().then((uid) => {
      if (cancelled) return;
      setUserId(uid);
      refresh(uid);
    });
    return () => { cancelled = true; };
  }, []);

  const handleSyncSaved = async () => {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const result = await libraryAPI.syncSaved(userId);
      if (result.status === 'not_configured' || result.status === 'error') {
        setMessage(result.message);
        return;
      }
      if (result.status === 'empty') {
        setMessage('No saved articles to index yet. Save a paper from a search result first.');
        return;
      }
      setMessage(`Indexed ${result.indexed} papers (${result.added} new, ${result.updated} updated) from ${result.saved_count} saved articles.`);
      await refresh(userId);
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Failed to index saved articles.');
    } finally {
      setLoading(false);
    }
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError('');
    setAnswer(null);
    try {
      const data = await libraryAPI.ask({ userId, question: question.trim() });
      setAnswer(data);
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Library ask failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleZoteroImport = async () => {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const data = await libraryAPI.importZotero({ userId });
      if (data.status === 'not_configured') {
        setMessage(data.message);
      } else if (data.status === 'error') {
        setError(data.message);
      } else {
        setMessage(`Imported ${data.imported} papers from Zotero (${data.fetched} fetched).`);
        await refresh(userId);
      }
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Zotero import failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleCheckAlerts = async () => {
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const data = await libraryAPI.checkAlerts({ userId, topics: topicInput ? [topicInput.trim()] : [] });
      if (data.status === 'no_topics') {
        setMessage('Save a topic first (type one below and check alerts).');
      } else {
        setMessage(`Checked ${data.topics.join(', ')} since ${data.since}: ${data.new_count} new papers.`);
        await refresh(userId);
      }
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Alerts check failed.');
    } finally {
      setLoading(false);
    }
  };

  const entityNodes = (graph?.nodes || []).filter((n) => n.type === 'entity');
  const paperNodes = (graph?.nodes || []).filter((n) => n.type === 'paper');
  const sharedEntities = graph?.shared_entities || [];

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-semibold text-black">My Library</h1>
        <p className="text-gray-600 mt-2">
          A private knowledge graph over your saved papers and notes. Everything is
          stored locally on this machine and indexed with the local model; no data
          leaves the machine. Index your saved articles, ask questions across them,
          import from Zotero, or export to BibTeX and RIS.
        </p>

        {message && <p className="mt-4 text-sm text-green-700">{message}</p>}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            onClick={handleSyncSaved}
            disabled={loading}
            className="px-4 py-2 bg-black text-white text-sm rounded-md disabled:opacity-50"
          >
            Index my saved papers
          </button>
          <button
            onClick={handleZoteroImport}
            disabled={loading}
            className="px-4 py-2 border border-gray-300 text-sm rounded-md disabled:opacity-50"
          >
            Import from Zotero
          </button>
          <a
            href={libraryAPI.exportUrl(userId, 'bibtex')}
            className="px-4 py-2 border border-gray-300 text-sm rounded-md"
            download
          >
            Export BibTeX
          </a>
          <a
            href={libraryAPI.exportUrl(userId, 'ris')}
            className="px-4 py-2 border border-gray-300 text-sm rounded-md"
            download
          >
            Export RIS
          </a>
        </div>

        <section className="mt-8">
          <h2 className="text-lg font-semibold text-black">
            Knowledge graph ({paperNodes.length} papers, {entityNodes.length} entities, {sharedEntities.length} shared)
          </h2>
          {papers.length === 0 ? (
            <p className="text-sm text-gray-600 mt-2">
              Your library is empty. Save papers from search results, then index them here.
            </p>
          ) : (
            <>
              <p className="text-sm text-gray-600 mt-2">
                Entities shared across papers link them together. Shared entities:{' '}
                {sharedEntities.length ? sharedEntities.join(', ') : 'none yet'}
              </p>
              <ul className="mt-3 space-y-2 text-sm text-gray-700">
                {papers.map((paper) => (
                  <li key={paper.key} className="border border-gray-200 rounded-lg p-3">
                    <p className="font-medium">{paper.title} ({paper.year || 'n.d.'})</p>
                    <p className="text-gray-600 mt-1">
                      Entities: {(paper.entities || []).join(', ') || 'none extracted'}
                    </p>
                    {paper.notes && <p className="text-gray-600">Notes: {paper.notes}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold text-black">Ask across my library</h2>
          <form onSubmit={handleAsk} className="mt-3 flex gap-2">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What do my saved papers say about sleep and memory?"
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
            <button type="submit" disabled={loading} className="px-4 py-2 bg-black text-white text-sm rounded-md disabled:opacity-50">
              Ask
            </button>
          </form>
          {answer && (
            <div className="mt-3 border border-gray-200 rounded-lg p-4">
              <p className="text-sm whitespace-pre-wrap">{answer.answer}</p>
              <p className="text-xs text-gray-500 mt-2">
                Sources: {(answer.sources || []).map((s) => s.title).join('; ') || 'none'}
                {' '}({answer.retrieval || 'keyword'} retrieval{answer.llm_used === false ? ', local model unavailable' : ''})
              </p>
            </div>
          )}
        </section>

        <section className="mt-8">
          <h2 className="text-lg font-semibold text-black">New-paper alerts</h2>
          <p className="text-sm text-gray-600 mt-1">
            Computed locally from the free OpenAlex API: each check only reports papers
            published since the last check. Saved topics: {topics.join(', ') || 'none yet'}
          </p>
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              value={topicInput}
              onChange={(e) => setTopicInput(e.target.value)}
              placeholder="Add a topic, e.g. sleep and memory"
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
            <button onClick={handleCheckAlerts} disabled={loading} className="px-4 py-2 bg-black text-white text-sm rounded-md disabled:opacity-50">
              Check for new papers
            </button>
          </div>
          <ul className="mt-3 space-y-2 text-sm text-gray-700">
            {alerts.length === 0 ? (
              <li className="text-gray-600">No new papers from the last check.</li>
            ) : (
              alerts.map((paper, i) => (
                <li key={i} className="border border-gray-200 rounded-lg p-3">
                  {paper.title} ({paper.publication_date || paper.year || 'n.d.'}) - topic: {paper.topic}
                  {paper.doi ? ` - doi:${paper.doi}` : ''}
                </li>
              ))
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}

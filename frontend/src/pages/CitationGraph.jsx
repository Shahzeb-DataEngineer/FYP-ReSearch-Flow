import React, { useState } from 'react';
import { gapFinderAPI, APIError } from '../services/api';

export default function CitationGraph() {
  const [doi, setDoi] = useState('10.1038/nature12373');
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleRun = async (e) => {
    e.preventDefault();
    if ((!doi.trim() && !topic.trim()) || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await gapFinderAPI.runGraph({
        doi: doi.trim(),
        topic: topic.trim(),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'Gap finder failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const graph = result?.graph || { nodes: [], edges: [] };
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const width = 900;
  const height = 520;
  const positions = new Map();
  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(1, nodes.length);
    const radius = node.isRoot ? 40 : 200;
    positions.set(node.id, {
      x: width / 2 + radius * Math.cos(angle),
      y: height / 2 + radius * Math.sin(angle) * 0.85,
    });
  });

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-semibold text-black">Citation Graph and Gap Finder</h1>
        <p className="text-gray-600 mt-2">
          Start from one paper DOI or a topic. The graph shows citing and cited papers
          from free OpenAlex and Semantic Scholar data, the timeline shows papers by
          year, and the gap finder lists under-cited recent work plus questions the
          collected literature does not yet answer. Every unanswered question names
          the papers it was checked against.
        </p>

        <form onSubmit={handleRun} className="mt-6 space-y-4 border border-gray-200 rounded-lg p-5">
          <div>
            <label className="block text-sm font-medium text-black mb-1" htmlFor="graph-doi">
              Seed paper DOI
            </label>
            <input
              id="graph-doi"
              type="text"
              value={doi}
              onChange={(e) => setDoi(e.target.value)}
              placeholder="10.1038/nature12373"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-black mb-1" htmlFor="graph-topic">
              Or a topic (used when no DOI is given)
            </label>
            <input
              id="graph-topic"
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="sleep and memory consolidation"
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-black text-white text-sm rounded-md disabled:opacity-50"
          >
            {loading ? 'Building graph (this takes a while)...' : 'Build graph and find gaps'}
          </button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>

        {result && result.status !== 'success' && (
          <p className="mt-6 text-sm text-gray-700">{result.message}</p>
        )}

        {result?.status === 'success' && (
          <div className="mt-8 space-y-8">
            <section>
              <h2 className="text-lg font-semibold text-black">
                Citation graph ({graph.stats?.totalNodes || nodes.length} papers, {graph.stats?.totalEdges || edges.length} links)
              </h2>
              <p className="text-sm text-gray-600 mt-1">
                Black nodes are seed papers. Took {result.processing_time_seconds}s.
              </p>
              <svg viewBox={`0 0 ${width} ${height}`} className="w-full border border-gray-200 rounded-lg mt-3">
                {edges.map((edge, i) => {
                  const a = positions.get(edge.source);
                  const b = positions.get(edge.target);
                  if (!a || !b) return null;
                  return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#cbd5e1" strokeWidth="1" />;
                })}
                {nodes.map((node) => {
                  const pos = positions.get(node.id);
                  const r = node.isRoot ? 12 : 6 + Math.min(6, (node.citationCount || 0) / 50);
                  return (
                    <g key={node.id}>
                      <circle cx={pos.x} cy={pos.y} r={r} fill={node.isRoot ? '#000' : '#3b82f6'} />
                      <title>{`${node.title} (${node.year || 'n.d.'}, ${node.citationCount || 0} citations)`}</title>
                    </g>
                  );
                })}
              </svg>
              <ul className="mt-3 space-y-1 text-sm text-gray-700">
                {nodes.slice(0, 10).map((node) => (
                  <li key={node.id}>
                    {node.isRoot ? <strong>Seed: </strong> : null}
                    {node.title} ({node.year || 'n.d.'}, {node.citationCount || 0} citations)
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-black">Timeline</h2>
              <table className="mt-3 w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
                <thead>
                  <tr className="bg-gray-50 text-left">
                    <th className="px-3 py-2">Year</th>
                    <th className="px-3 py-2">Papers</th>
                    <th className="px-3 py-2">Total citations</th>
                    <th className="px-3 py-2">Avg citations</th>
                    <th className="px-3 py-2">Top paper</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.timeline || []).map((row) => (
                    <tr key={row.year} className="border-t border-gray-200">
                      <td className="px-3 py-2">{row.year}</td>
                      <td className="px-3 py-2">{row.paper_count}</td>
                      <td className="px-3 py-2">{row.total_citations}</td>
                      <td className="px-3 py-2">{row.avg_citations}</td>
                      <td className="px-3 py-2">{row.top_paper}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>

            <section>
              <h2 className="text-lg font-semibold text-black">Under-cited clusters</h2>
              {(result.under_cited_clusters || []).length === 0 ? (
                <p className="text-sm text-gray-600 mt-2">
                  No under-cited cluster found: a cluster needs a recent year with at
                  least 3 papers and some below that year's median citation count.
                </p>
              ) : (
                (result.under_cited_clusters || []).map((cluster) => (
                  <div key={cluster.year} className="mt-3 border border-gray-200 rounded-lg p-4">
                    <p className="text-sm font-medium">
                      {cluster.year}: {cluster.paper_count} papers, median {cluster.median_citations} citations
                    </p>
                    <ul className="mt-2 space-y-1 text-sm text-gray-700">
                      {cluster.under_cited.map((paper, i) => (
                        <li key={i}>
                          {paper.title} ({paper.citation_count} citations)
                          {paper.doi ? ` - doi:${paper.doi}` : ''}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))
              )}
            </section>

            <section>
              <h2 className="text-lg font-semibold text-black">Unanswered questions</h2>
              <p className="text-sm text-gray-600 mt-1">
                {result.unanswered_questions?.llm_used
                  ? 'Found by the local model from the collected abstracts.'
                  : 'Local model unavailable, so these are fallback questions tied to the papers checked.'}
              </p>
              <ul className="mt-3 space-y-4">
                {(result.unanswered_questions?.questions || []).map((item, i) => (
                  <li key={i} className="border border-gray-200 rounded-lg p-4">
                    <p className="text-sm font-medium">{item.question}</p>
                    <p className="text-sm text-gray-600 mt-1">{item.why_unanswered}</p>
                    <p className="text-xs text-gray-500 mt-2">
                      Checked against:{' '}
                      {(item.checked_papers || []).map((p) => p.title).join('; ')}
                    </p>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

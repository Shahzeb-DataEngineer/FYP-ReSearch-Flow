import React, { useState } from 'react';
import { prismaAPI, APIError } from '../services/api';

const splitCriteria = (text) =>
  text.split('\n').map((line) => line.trim()).filter(Boolean);

export default function PrismaReview() {
  const [question, setQuestion] = useState('');
  const [inclusion, setInclusion] = useState('randomized trial\nadult participants');
  const [exclusion, setExclusion] = useState('animal studies');
  const [maxPapers, setMaxPapers] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const handleRun = async (e) => {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await prismaAPI.runPrisma({
        question: question.trim(),
        inclusionCriteria: splitCriteria(inclusion),
        exclusionCriteria: splitCriteria(exclusion),
        maxPapers: Number(maxPapers),
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof APIError ? err.message : 'PRISMA review failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const flow = result?.prisma_flow;
  const flowSteps = flow
    ? [
        { label: 'Identified', value: flow.identified },
        { label: 'Screened', value: flow.screened },
        { label: 'Excluded', value: flow.excluded },
        { label: 'Included', value: flow.included },
        { label: 'Pass disagreements', value: flow.disagreements },
      ]
    : [];

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <h1 className="text-2xl font-semibold text-black">PRISMA Systematic Review</h1>
        <p className="text-gray-600 mt-2">
          Free systematic review: multi-source search, dual-pass AI screening with
          adjudication, and PRISMA flow counts. AI screening is a first pass only;
          verify every decision yourself before relying on it.
        </p>

        <form onSubmit={handleRun} className="mt-6 space-y-4 border border-gray-200 rounded-lg p-5">
          <div>
            <label className="block text-sm font-medium text-black mb-1" htmlFor="prisma-question">
              Research question
            </label>
            <input
              id="prisma-question"
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Does sleep deprivation impair memory consolidation in adults?"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
            />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-black mb-1" htmlFor="prisma-inclusion">
                Inclusion criteria (one per line)
              </label>
              <textarea
                id="prisma-inclusion"
                rows={3}
                value={inclusion}
                onChange={(e) => setInclusion(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-black mb-1" htmlFor="prisma-exclusion">
                Exclusion criteria (one per line)
              </label>
              <textarea
                id="prisma-exclusion"
                rows={3}
                value={exclusion}
                onChange={(e) => setExclusion(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm"
              />
            </div>
          </div>
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-black" htmlFor="prisma-max">
              Max papers to screen
            </label>
            <select
              id="prisma-max"
              value={maxPapers}
              onChange={(e) => setMaxPapers(e.target.value)}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            >
              {[5, 8, 10].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="px-4 py-2 bg-black hover:bg-gray-800 text-white rounded text-sm disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Screening... this takes minutes on CPU' : 'Run PRISMA review'}
            </button>
          </div>
          {loading && (
            <p className="text-sm text-gray-600">
              Searching free sources and screening each paper twice with the local model.
              Do not close this page.
            </p>
          )}
          {error && <p className="text-sm text-red-600">{error}</p>}
        </form>

        {result && (
          <div className="mt-8 space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-black">PRISMA flow</h2>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-3">
                {flowSteps.map((step) => (
                  <div key={step.label} className="border border-gray-200 rounded-lg p-4 text-center">
                    <div className="text-2xl font-bold text-black">{step.value}</div>
                    <div className="text-xs text-gray-600 mt-1">{step.label}</div>
                  </div>
                ))}
              </div>
              {flow?.excluded_by_reason && Object.keys(flow.excluded_by_reason).length > 0 && (
                <ul className="mt-3 text-sm text-gray-700 list-disc list-inside">
                  {Object.entries(flow.excluded_by_reason).map(([reason, count]) => (
                    <li key={reason}>{reason}: {count}</li>
                  ))}
                </ul>
              )}
              <p className="text-sm text-gray-600 mt-3">
                Processed in {result.processing_time_seconds}s.
                {result.message ? ` ${result.message}` : ''}
              </p>
            </div>

            {result.screening_accuracy_note && (
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">
                {result.screening_accuracy_note}
              </p>
            )}

            <div>
              <h2 className="text-lg font-semibold text-black">Screening table</h2>
              {result.screening?.length === 0 ? (
                <p className="text-sm text-gray-600 mt-2">No papers were screened.</p>
              ) : (
                <div className="overflow-x-auto mt-3">
                  <table className="w-full text-sm border border-gray-200">
                    <thead>
                      <tr className="bg-gray-50 text-left">
                        <th className="border-b border-gray-200 px-3 py-2">Paper</th>
                        <th className="border-b border-gray-200 px-3 py-2">Pass 1</th>
                        <th className="border-b border-gray-200 px-3 py-2">Pass 2</th>
                        <th className="border-b border-gray-200 px-3 py-2">Final</th>
                        <th className="border-b border-gray-200 px-3 py-2">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.screening.map((row, idx) => (
                        <tr key={idx} className="align-top">
                          <td className="border-b border-gray-200 px-3 py-2">
                            <div className="font-medium text-black">{row.title}</div>
                            <div className="text-xs text-gray-500">
                              {row.year || ''} {row.venue ? ` · ${row.venue}` : ''}
                              {row.doi ? ` · ${row.doi}` : ''}
                            </div>
                            {row.disagreement && (
                              <span className="inline-block mt-1 text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                                Passes disagreed - human review needed
                              </span>
                            )}
                          </td>
                          <td className="border-b border-gray-200 px-3 py-2 capitalize">{row.pass1_decision}</td>
                          <td className="border-b border-gray-200 px-3 py-2 capitalize">{row.pass2_decision}</td>
                          <td className="border-b border-gray-200 px-3 py-2 capitalize font-medium">{row.final_decision}</td>
                          <td className="border-b border-gray-200 px-3 py-2 text-gray-700">{row.final_reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

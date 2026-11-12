import React, { useState, useEffect } from 'react';
import { X, CheckCircle, Loader2, AlertCircle, MessageSquare, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * FloatingBubbles — displays background AI summarization jobs as floating pills.
 *
 * Props:
 *   summaryJobs  — Map<paperId, { paperId, paper, status, summary, error, startedAt }>
 *   onBubbleClick — (paperId) => void  — opens the DetailPanel for that paper
 *   onDismiss     — (paperId) => void  — removes the job from the map
 */
const FloatingBubbles = ({ summaryJobs, onBubbleClick, onDismiss }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [dismissedIds, setDismissedIds] = useState(new Set());
  const [, setTick] = useState(0);

  // Convert map to array, filter out dismissed, sort by startedAt (newest first)
  const jobs = Array.from(summaryJobs.values())
    .filter(job => !dismissedIds.has(job.paperId))
    .sort((a, b) => b.startedAt - a.startedAt);

  const loadingCount = jobs.filter(j => j.status === 'loading').length;
  const doneCount = jobs.filter(j => j.status === 'done').length;
  const errorCount = jobs.filter(j => j.status === 'error').length;

  // Auto-refresh elapsed time for loading jobs
  useEffect(() => {
    if (loadingCount > 0) {
      const interval = setInterval(() => setTick(t => t + 1), 1000);
      return () => clearInterval(interval);
    }
  }, [loadingCount]);

  // Nothing to show
  if (jobs.length === 0) return null;

  const MAX_VISIBLE = 5;
  const visibleJobs = collapsed ? [] : jobs.slice(0, MAX_VISIBLE);
  const hiddenCount = Math.max(0, jobs.length - MAX_VISIBLE);

  const handleDismiss = (e, paperId) => {
    e.stopPropagation();
    setDismissedIds(prev => new Set([...prev, paperId]));
    if (onDismiss) onDismiss(paperId);
  };

  const truncateTitle = (title, maxLen = 35) => {
    if (!title) return 'Untitled Paper';
    return title.length > maxLen ? title.substring(0, maxLen) + '…' : title;
  };

  const getElapsedTime = (startedAt) => {
    const seconds = Math.floor((Date.now() - startedAt) / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  return (
    <div
      className="fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-2"
      style={{ maxWidth: '380px' }}
    >
      {/* Bubble List */}
      <div
        className="flex flex-col gap-2 w-full transition-all duration-300"
        style={{
          maxHeight: collapsed ? '0px' : '500px',
          overflow: 'hidden',
          opacity: collapsed ? 0 : 1,
        }}
      >
        {visibleJobs.map((job) => (
          <div
            key={job.paperId}
            onClick={() => {
              if (job.status === 'done' || job.status === 'error') {
                onBubbleClick(job.paperId);
              }
            }}
            className={`
              group relative flex items-center gap-3 px-4 py-3 rounded-2xl
              border shadow-lg cursor-pointer
              transition-all duration-300 ease-out
              hover:scale-[1.02] hover:shadow-xl
              backdrop-blur-lg
              ${job.status === 'loading'
                ? 'bg-white/95 border-blue-200 hover:border-blue-300'
                : job.status === 'done'
                  ? 'bg-white/95 border-emerald-200 hover:border-emerald-400 summary-bubble-done'
                  : 'bg-white/95 border-red-200 hover:border-red-300'
              }
            `}
            style={{
              animation: 'bubbleSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards',
              minWidth: '280px',
            }}
          >
            {/* Status Icon */}
            <div className={`
              flex-shrink-0 w-9 h-9 rounded-xl flex items-center justify-center
              ${job.status === 'loading'
                ? 'bg-blue-50'
                : job.status === 'done'
                  ? 'bg-emerald-50'
                  : 'bg-red-50'
              }
            `}>
              {job.status === 'loading' ? (
                <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
              ) : job.status === 'done' ? (
                <CheckCircle className="w-5 h-5 text-emerald-500" />
              ) : (
                <AlertCircle className="w-5 h-5 text-red-500" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium truncate ${
                job.status === 'done' ? 'text-emerald-800' : job.status === 'error' ? 'text-red-800' : 'text-gray-800'
              }`}>
                {truncateTitle(job.paper?.title)}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {job.status === 'loading'
                  ? `Summarizing… ${getElapsedTime(job.startedAt)}`
                  : job.status === 'done'
                    ? 'Summary ready — click to view'
                    : `Error: ${job.error || 'Failed'}`
                }
              </p>
            </div>

            {/* Dismiss Button */}
            <button
              onClick={(e) => handleDismiss(e, job.paperId)}
              className="flex-shrink-0 p-1 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-gray-100 transition-all duration-200"
              title="Dismiss"
            >
              <X className="w-3.5 h-3.5 text-gray-400" />
            </button>

            {/* Glow effect for done state */}
            {job.status === 'done' && (
              <div className="absolute inset-0 rounded-2xl ring-2 ring-emerald-300/40 animate-pulse pointer-events-none" />
            )}
          </div>
        ))}

        {/* Hidden count indicator */}
        {hiddenCount > 0 && !collapsed && (
          <div className="text-xs text-gray-500 text-right pr-2 font-medium">
            +{hiddenCount} more summarization{hiddenCount > 1 ? 's' : ''}
          </div>
        )}
      </div>

      {/* Summary Header Pill — always visible when there are jobs */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className={`
          flex items-center gap-2.5 px-4 py-2.5 rounded-2xl
          border shadow-lg backdrop-blur-lg
          transition-all duration-300 ease-out
          hover:shadow-xl hover:scale-[1.02]
          ${doneCount > 0 && loadingCount === 0
            ? 'bg-emerald-50/95 border-emerald-200 text-emerald-800'
            : errorCount > 0 && loadingCount === 0
              ? 'bg-red-50/95 border-red-200 text-red-800'
              : 'bg-white/95 border-gray-200 text-gray-800'
          }
        `}
      >
        <MessageSquare className="w-4 h-4" />
        <span className="text-sm font-semibold">
          {loadingCount > 0 && (
            <span className="inline-flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              {loadingCount} processing
            </span>
          )}
          {loadingCount > 0 && doneCount > 0 && ' · '}
          {doneCount > 0 && (
            <span className="text-emerald-600">{doneCount} ready</span>
          )}
          {(loadingCount > 0 || doneCount > 0) && errorCount > 0 && ' · '}
          {errorCount > 0 && (
            <span className="text-red-600">{errorCount} failed</span>
          )}
          {loadingCount === 0 && doneCount === 0 && errorCount === 0 && 'Summaries'}
        </span>
        {collapsed ? (
          <ChevronUp className="w-3.5 h-3.5" />
        ) : (
          <ChevronDown className="w-3.5 h-3.5" />
        )}
      </button>
    </div>
  );
};

export default FloatingBubbles;

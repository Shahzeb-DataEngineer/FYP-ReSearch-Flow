import { useEffect, useState } from 'react';
import { modelsAPI } from '../services/api';

/**
 * Cost meter panel (Move 7): per-task tokens and wall time recorded
 * by the backend, the cloud price the same tokens would have cost
 * at the published GPT-4o-mini rate, and total spent, always $0.00.
 */
export default function UsagePanel() {
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    modelsAPI.getUsage()
      .then((data) => setUsage(data))
      .catch((e) => setError(e.message || 'Could not load usage.'));
  }, []);

  if (error) {
    return (
      <div className="bg-surface border border-faint rounded-2xl p-4 text-left">
        <h3 className="text-sm font-semibold text-ink mb-1">Usage and cost</h3>
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }
  if (!usage) {
    return (
      <div className="bg-surface border border-faint rounded-2xl p-4 text-left">
        <h3 className="text-sm font-semibold text-ink">Usage and cost</h3>
        <p className="text-sm text-muted">Loading usage...</p>
      </div>
    );
  }

  return (
    <div className="bg-surface border border-faint rounded-2xl p-4 text-left">
      <h3 className="text-sm font-semibold text-ink mb-1">Usage and cost</h3>
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div>
          <div className="text-2xl font-bold text-ink">{usage.total_tokens.toLocaleString()}</div>
          <div className="text-xs text-muted">tokens used (estimated)</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-success">$0.00</div>
          <div className="text-xs text-muted">total spent - local models only</div>
        </div>
        <div>
          <div className="text-lg font-semibold text-ink">
            ${Number(usage.cloud_price_avoided_usd || 0).toFixed(4)}
          </div>
          <div className="text-xs text-muted">cloud price avoided</div>
        </div>
        <div>
          <div className="text-lg font-semibold text-ink">
            {Math.round(usage.total_seconds || 0)}s
          </div>
          <div className="text-xs text-muted">total model time, {usage.total_calls} calls</div>
        </div>
      </div>
      {usage.by_task && usage.by_task.length > 0 && (
        <table className="w-full text-xs text-muted">
          <thead>
            <tr className="text-left text-muted border-b border-faint">
              <th className="py-1 pr-2">Task</th>
              <th className="py-1 pr-2">Calls</th>
              <th className="py-1 pr-2">Tokens</th>
              <th className="py-1">Time</th>
            </tr>
          </thead>
          <tbody>
            {usage.by_task.map((row) => (
              <tr key={row.task} className="border-b border-faint">
                <td className="py-1 pr-2">{row.task}</td>
                <td className="py-1 pr-2">{row.calls}</td>
                <td className="py-1 pr-2">{Number(row.total_tokens).toLocaleString()}</td>
                <td className="py-1">{Math.round(row.seconds)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-[11px] text-muted mt-2">
        Cloud price avoided uses the {usage.cloud_rate?.model} rate: $
        {usage.cloud_rate?.input_usd_per_million_tokens} per 1M input tokens and $
        {usage.cloud_rate?.output_usd_per_million_tokens} per 1M output tokens
        ({usage.cloud_rate?.source}). Token counts are estimates.
      </p>
    </div>
  );
}

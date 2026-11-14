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
      <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
        <h3 className="text-sm font-semibold text-gray-800 mb-1">Usage and cost</h3>
        <p className="text-sm text-red-600">{error}</p>
      </div>
    );
  }
  if (!usage) {
    return (
      <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
        <h3 className="text-sm font-semibold text-gray-800">Usage and cost</h3>
        <p className="text-sm text-gray-500">Loading usage...</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 text-left">
      <h3 className="text-sm font-semibold text-gray-800 mb-1">Usage and cost</h3>
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div>
          <div className="text-2xl font-bold text-black">{usage.total_tokens.toLocaleString()}</div>
          <div className="text-xs text-gray-500">tokens used (estimated)</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-emerald-700">$0.00</div>
          <div className="text-xs text-gray-500">total spent - local models only</div>
        </div>
        <div>
          <div className="text-lg font-semibold text-black">
            ${Number(usage.cloud_price_avoided_usd || 0).toFixed(4)}
          </div>
          <div className="text-xs text-gray-500">cloud price avoided</div>
        </div>
        <div>
          <div className="text-lg font-semibold text-black">
            {Math.round(usage.total_seconds || 0)}s
          </div>
          <div className="text-xs text-gray-500">total model time, {usage.total_calls} calls</div>
        </div>
      </div>
      {usage.by_task && usage.by_task.length > 0 && (
        <table className="w-full text-xs text-gray-700">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-1 pr-2">Task</th>
              <th className="py-1 pr-2">Calls</th>
              <th className="py-1 pr-2">Tokens</th>
              <th className="py-1">Time</th>
            </tr>
          </thead>
          <tbody>
            {usage.by_task.map((row) => (
              <tr key={row.task} className="border-b border-gray-100">
                <td className="py-1 pr-2">{row.task}</td>
                <td className="py-1 pr-2">{row.calls}</td>
                <td className="py-1 pr-2">{Number(row.total_tokens).toLocaleString()}</td>
                <td className="py-1">{Math.round(row.seconds)}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-[11px] text-gray-400 mt-2">
        Cloud price avoided uses the {usage.cloud_rate?.model} rate: $
        {usage.cloud_rate?.input_usd_per_million_tokens} per 1M input tokens and $
        {usage.cloud_rate?.output_usd_per_million_tokens} per 1M output tokens
        ({usage.cloud_rate?.source}). Token counts are estimates.
      </p>
    </div>
  );
}

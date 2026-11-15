import { useEffect, useState } from 'react';
import { modelsAPI } from '../services/api';

/**
 * Model picker (Move 7): shows the local Ollama models actually
 * installed, with size and context, and lets the researcher switch
 * the active chat model. The backend validates the choice against
 * the installed list and persists it locally.
 */
export default function ModelPicker() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const result = await modelsAPI.listModels();
      setData(result);
      setError('');
    } catch (e) {
      setError(e.message || 'Could not load local models.');
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (error) {
    return (
      <div className="bg-surface border border-faint rounded-2xl p-4 text-left">
        <h3 className="text-sm font-semibold text-ink mb-1">Local model</h3>
        <p className="text-sm text-danger">{error}</p>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="bg-surface border border-faint rounded-2xl p-4 text-left">
        <h3 className="text-sm font-semibold text-ink">Local model</h3>
        <p className="text-sm text-muted">Loading installed models...</p>
      </div>
    );
  }

  const active = data.models.find((m) => m.name === data.active_chat_model);

  return (
    <div className="bg-surface border border-faint rounded-2xl p-4 text-left">
      <h3 className="text-sm font-semibold text-ink mb-1">Local model</h3>
      <p className="text-xs text-muted mb-3">
        Runs on this machine with Ollama. No cloud model is ever used, so model use costs $0.00.
      </p>
      {data.ollama_available ? (
        <>
          <label className="text-xs font-medium text-ink" htmlFor="model-picker-select">
            Chat model
          </label>
          <select
            id="model-picker-select"
            value={data.active_chat_model}
            disabled={saving}
            onChange={async (e) => {
              setSaving(true);
              try {
                const result = await modelsAPI.selectModel(e.target.value, 'chat');
                setData((prev) => ({ ...prev, active_chat_model: result.active_model }));
              } catch (err) {
                setError(err.message || 'Could not switch model.');
              } finally {
                setSaving(false);
              }
            }}
            className="mt-1 w-full bg-surface border border-faint rounded-lg px-2 py-1.5 text-sm text-ink focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent/20"
          >
            {data.chat_models.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
          {active && (
            <p className="text-xs text-muted mt-2">
              {active.parameter_size || 'unknown size'} parameters
              {active.size_mb ? `, ${active.size_mb} MB` : ''}
              {active.context_length ? `, ${active.context_length.toLocaleString()} context tokens` : ''}
            </p>
          )}
          <p className="text-xs text-muted mt-1">
            Embedding model: {data.active_embed_model}
          </p>
          {data.models.length > 1 && (
            <p className="text-xs text-muted mt-1">
              Also installed: {data.models.map((m) => m.name).join(', ')}
            </p>
          )}
        </>
      ) : (
        <p className="text-sm text-warn bg-warn-bg border border-faint rounded-lg px-3 py-2">
          The local Ollama server is not reachable. Start Ollama to pick a model.
        </p>
      )}
    </div>
  );
}

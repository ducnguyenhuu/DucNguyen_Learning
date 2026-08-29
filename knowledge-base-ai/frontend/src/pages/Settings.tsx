/**
 * Settings page — displays current application configuration from GET /config.
 * All values are read-only; settings are changed via the .env file and server restart.
 */
import { useEffect, useState } from 'react';
import { getConfig } from '../services/api';
import type { ConfigResponse } from '../services/types';
import LoadingSpinner from '../components/common/LoadingSpinner';

function ConfigRow({ label, value }: { label: string; value: string | number }) {
  return (
    <tr>
      <th scope="row" className="config-key">
        {label}
      </th>
      <td className="config-value">{String(value)}</td>
    </tr>
  );
}

export default function Settings() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getConfig()
      .then((cfg) => {
        setConfig(cfg);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load configuration';
        setError(msg);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  return (
    <div className="page page--settings">
      <h1>Settings</h1>
      <p className="subtitle">
        Current application configuration. To change values, edit{' '}
        <code>backend/.env</code> and restart the server.
      </p>

      {isLoading && <LoadingSpinner label="Loading configuration…" />}
      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      {config && (
        <table className="config-table" aria-label="Application configuration">
          <caption className="sr-only">Application configuration values</caption>
          <tbody>
            <ConfigRow label="Host" value={config.host} />
            <ConfigRow label="Port" value={config.port} />
            <ConfigRow label="Embedding Provider" value={config.embedding_provider} />
            <ConfigRow label="Embedding Model" value={config.embedding_model} />
            <ConfigRow label="Embedding Dimensions" value={config.embedding_dimensions} />
            <ConfigRow label="LLM Provider" value={config.llm_provider} />
            <ConfigRow label="LLM Model" value={config.llm_model} />
            <ConfigRow label="LLM Base URL" value={config.llm_base_url} />
            <ConfigRow label="LLM Context Window" value={config.llm_context_window} />
            <ConfigRow label="Retrieval Top-K" value={config.retrieval_top_k} />
            <ConfigRow
              label="Similarity Threshold"
              value={config.retrieval_similarity_threshold}
            />
            <ConfigRow label="Chunk Size" value={config.chunk_size} />
            <ConfigRow label="Chunk Overlap" value={config.chunk_overlap} />
            <ConfigRow label="Sliding Window Messages" value={config.sliding_window_messages} />
            <ConfigRow label="ChromaDB Collection" value={config.chroma_collection_name} />
            <ConfigRow label="Log Level" value={config.log_level} />
          </tbody>
        </table>
      )}
    </div>
  );
}

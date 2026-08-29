/**
 * Dashboard — landing page with stats, recent conversations, and quick actions.
 * Implements frontend-contract.md §2.3.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHealth, listConversations, listDocuments } from '../services/api';
import type { Conversation, HealthResponse } from '../services/types';

export default function Dashboard() {
  const navigate = useNavigate();

  const [docCount, setDocCount] = useState<number | null>(null);
  const [convCount, setConvCount] = useState<number | null>(null);
  const [recentConvs, setRecentConvs] = useState<Conversation[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      listDocuments({ page: 1, page_size: 1 }),
      listConversations(),
      getHealth(),
    ])
      .then(([docsResp, convsResp, healthResp]) => {
        setDocCount(docsResp.total);
        setConvCount(convsResp.total);
        setRecentConvs(convsResp.conversations.slice(0, 5));
        setHealth(healthResp);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load dashboard data';
        setError(msg);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div data-testid="dashboard" className="page page--dashboard">
      <h1>Knowledge Base AI</h1>
      <p className="subtitle">Your local document intelligence hub</p>

      {loading && (
        <p data-testid="dashboard-loading" aria-live="polite">
          Loading…
        </p>
      )}

      {!loading && error && (
        <p data-testid="dashboard-error" role="alert" className="error-message">
          {error}
        </p>
      )}

      {!loading && !error && (
        <>
          {/* Stats cards */}
          <div className="stats-grid">
            <div data-testid="stat-docs" className="stat-card">
              <span className="stat-value">{docCount ?? '—'}</span>
              <span className="stat-label">Documents</span>
            </div>

            <div data-testid="stat-conversations" className="stat-card">
              <span className="stat-value">{convCount ?? '—'}</span>
              <span className="stat-label">Conversations</span>
            </div>

            <div data-testid="stat-health" className="stat-card">
              <span
                className={`stat-value ${health?.status === 'ok' ? 'status-ok' : 'status-warn'}`}
              >
                {health?.status === 'ok' ? 'OK' : 'Degraded'}
              </span>
              <span className="stat-label">
                Models: {health?.ollama === 'ok' ? '✓' : '⚠'}
              </span>
            </div>
          </div>

          {/* Recent conversations */}
          <section data-testid="recent-conversations" className="recent-conversations">
            <h2>Recent Conversations</h2>
            {recentConvs.length === 0 ? (
              <p data-testid="no-recent-conversations">No conversations yet.</p>
            ) : (
              <ul>
                {recentConvs.map((conv) => (
                  <li key={conv.id} data-testid="recent-conversation-item">
                    <button
                      className="conv-link"
                      onClick={() => navigate(`/chat/${conv.id}`)}
                    >
                      {conv.title ?? 'Untitled conversation'}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Quick actions */}
          <section className="quick-actions">
            <h2>Quick Actions</h2>
            <button className="btn btn--primary" data-testid="btn-new-chat" onClick={() => navigate('/chat')}>
              + New Chat
            </button>
            <button className="btn btn--secondary" data-testid="btn-ingest-docs" onClick={() => navigate('/documents')}>
              Ingest Docs
            </button>
            <button className="btn btn--secondary" data-testid="btn-settings" onClick={() => navigate('/settings')}>
              Settings
            </button>
          </section>
        </>
      )}
    </div>
  );
}

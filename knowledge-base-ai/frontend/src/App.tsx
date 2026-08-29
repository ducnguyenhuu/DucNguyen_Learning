/**
 * Root component with React Router configuration.
 *
 * Routes (per frontend-contract.md §1)
 * --------------------------------------
 * /                      → Dashboard (landing page)
 * /chat                  → ChatView (new conversation)
 * /chat/:conversationId  → ChatView (existing conversation)
 * /documents             → DocumentList
 * /documents/:documentId → DocumentDetail
 * /settings              → Settings
 *
 * Error Boundaries (per frontend-contract.md §6 & Constitution §I):
 *  - Global ErrorBoundary wraps the entire app for catastrophic failures
 *  - Per-route ErrorBoundary wraps each route so one page failure
 *    does not bring down the entire application
 */
import { lazy, Suspense } from 'react';
import { ErrorBoundary, type FallbackProps } from 'react-error-boundary';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/common/Layout';
import RouteErrorFallback from './components/common/RouteErrorFallback';
import LoadingSpinner from './components/common/LoadingSpinner';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';

// Lazy-loaded pages
const ChatView = lazy(() => import('./pages/ChatView'));
const DocumentList = lazy(() => import('./pages/DocumentList'));
const DocumentDetail = lazy(() => import('./pages/DocumentDetail'));

/** Top-level fallback — only reached if Layout itself crashes */
function GlobalErrorFallback({ error }: FallbackProps) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="error-boundary">
      <h2>Application Error</h2>
      <p>{message}</p>
      <button onClick={() => window.location.reload()} type="button">
        Reload page
      </button>
    </div>
  );
}

/** Helper: wrap a route element in a per-route ErrorBoundary + Suspense */
function RouteElement({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary FallbackComponent={RouteErrorFallback}>
      <Suspense fallback={<LoadingSpinner />}>{children}</Suspense>
    </ErrorBoundary>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary FallbackComponent={GlobalErrorFallback}>
        <Routes>
          <Route element={<Layout />}>
            <Route
              index
              element={
                <RouteElement>
                  <Dashboard />
                </RouteElement>
              }
            />
            <Route
              path="chat"
              element={
                <RouteElement>
                  <ChatView />
                </RouteElement>
              }
            />
            <Route
              path="chat/:conversationId"
              element={
                <RouteElement>
                  <ChatView />
                </RouteElement>
              }
            />
            <Route
              path="documents"
              element={
                <RouteElement>
                  <DocumentList />
                </RouteElement>
              }
            />
            <Route
              path="documents/:documentId"
              element={
                <RouteElement>
                  <DocumentDetail />
                </RouteElement>
              }
            />
            <Route
              path="settings"
              element={
                <RouteElement>
                  <Settings />
                </RouteElement>
              }
            />
            {/* Catch-all redirect to dashboard */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
}

export default App;

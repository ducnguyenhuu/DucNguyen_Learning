/**
 * ChatView — full chat interface (T053 / T057).
 * Provides a 3-column layout: ConversationSidebar | chat area | SourcePanel
 * Route: /chat (new conversation) and /chat/:conversationId (existing)
 */
import { useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ChatInput } from '../components/chat/ChatInput';
import { ConversationSidebar } from '../components/chat/ConversationSidebar';
import { MessageBubble } from '../components/chat/MessageBubble';
import { SourcePanel } from '../components/chat/SourcePanel';
import { useChat } from '../hooks/useChat';

const EXAMPLE_PROMPTS = [
  'What are the key topics covered in my documents?',
  'Summarize the most recent document I uploaded.',
  'Find information about a specific subject.',
];

export default function ChatView() {
  const { conversationId } = useParams<{ conversationId?: string }>();
  const navigate = useNavigate();

  const {
    messages,
    streaming,
    error,
    activeSources,
    setActiveSources,
    sendMessage,
    activeConversationId,
    clearError,
  } = useChat(conversationId ?? null);

  // Navigate to the conversation URL once a new conversation is created
  useEffect(() => {
    if (activeConversationId && !conversationId) {
      navigate(`/chat/${activeConversationId}`, { replace: true });
    }
  }, [activeConversationId, conversationId, navigate]);

  // Auto-scroll to latest message
  const messagesEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-view" data-testid="chat-view">
      <ConversationSidebar
        activeConversationId={conversationId ?? activeConversationId}
        onSelectConversation={(id) => navigate(`/chat/${id}`)}
        onNewChat={() => navigate('/chat')}
        onActiveConversationDeleted={() => navigate('/chat')}
      />

      <main className="chat-view__main">
        {error && (
          <div className="chat-view__error" role="alert">
            {error}
            <button
              className="chat-view__error-dismiss"
              type="button"
              aria-label="Dismiss error"
              onClick={clearError}
            >
              ×
            </button>
          </div>
        )}

        <div className="chat-view__messages" data-testid="messages-area">
          {messages.length === 0 ? (
            <div className="chat-view__welcome" data-testid="welcome-message">
              <h2>Ask anything about your documents</h2>
              <ul className="chat-view__examples" data-testid="example-prompts">
                {EXAMPLE_PROMPTS.map((prompt) => (
                  <li key={prompt}>
                    <button
                      type="button"
                      className="chat-view__example-btn"
                      onClick={() => void sendMessage(prompt)}
                    >
                      {prompt}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div data-testid="message-list">
              {messages.map((msg) => (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  onSourceClick={setActiveSources}
                />
              ))}
              {streaming && (
                <div
                  className="chat-view__typing-indicator"
                  aria-label="Generating response…"
                  data-testid="typing-indicator"
                />
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <ChatInput
          onSend={(content) => void sendMessage(content)}
          disabled={streaming}
          placeholder="Ask a question about your documents…"
        />
      </main>

      <SourcePanel
        sources={activeSources}
        onClose={() => setActiveSources([])}
      />
    </div>
  );
}

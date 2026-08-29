/**
 * WebSocket manager — connect, disconnect, auto-reconnect with exponential backoff,
 * and per-message-type handlers.
 *
 * Usage
 * -----
 * ```ts
 * const ws = new WebSocketManager('/api/v1/ingestion/progress/job-id');
 * ws.onMessage('progress', (msg) => console.log(msg));
 * ws.connect();
 * // … later …
 * ws.disconnect();
 * ```
 */

export type MessageHandler<T = unknown> = (data: T) => void;

interface WebSocketOptions {
  /** Base path prefix for all WebSocket URLs (default: window.location.host) */
  baseUrl?: string;
  /** Maximum reconnect attempts before giving up (default: 5) */
  maxRetries?: number;
  /** Initial reconnect delay in ms (default: 1000) */
  initialDelay?: number;
  /** Multiplier for exponential backoff (default: 2) */
  backoffFactor?: number;
}

export class WebSocketManager {
  private socket: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private retryCount = 0;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private isIntentionallyClosed = false;

  private readonly path: string;
  private readonly maxRetries: number;
  private readonly initialDelay: number;
  private readonly backoffFactor: number;

  constructor(path: string, options: WebSocketOptions = {}) {
    this.path = path;
    this.maxRetries = options.maxRetries ?? 5;
    this.initialDelay = options.initialDelay ?? 1000;
    this.backoffFactor = options.backoffFactor ?? 2;
  }

  // ---------------------------------------------------------------------------
  // Connection management
  // ---------------------------------------------------------------------------

  connect(): void {
    this.isIntentionallyClosed = false;
    this.retryCount = 0;
    this._open();
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;
    this._clearRetryTimeout();
    if (this.socket) {
      this.socket.close(1000, 'Intentional disconnect');
      this.socket = null;
    }
  }

  private _open(): void {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}${this.path}`;

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.retryCount = 0;
      this._emit('__open', null);
    };

    this.socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const data: unknown = JSON.parse(event.data);
        if (data && typeof data === 'object' && 'type' in data) {
          const typed = data as { type: string };
          this._emit(typed.type, data);
        }
        this._emit('__message', data);
      } catch {
        // Ignore non-JSON messages
      }
    };

    this.socket.onerror = () => {
      this._emit('__error', null);
    };

    this.socket.onclose = (event: CloseEvent) => {
      this._emit('__close', event);
      if (!this.isIntentionallyClosed && event.code !== 1000) {
        this._scheduleReconnect();
      }
    };
  }

  // ---------------------------------------------------------------------------
  // Auto-reconnect with exponential backoff
  // ---------------------------------------------------------------------------

  private _scheduleReconnect(): void {
    if (this.retryCount >= this.maxRetries) {
      this._emit('__max_retries', null);
      return;
    }
    const delay =
      this.initialDelay * Math.pow(this.backoffFactor, this.retryCount);
    this.retryCount += 1;
    this.retryTimeout = setTimeout(() => {
      this._open();
    }, delay);
  }

  private _clearRetryTimeout(): void {
    if (this.retryTimeout !== null) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
  }

  // ---------------------------------------------------------------------------
  // Message sending
  // ---------------------------------------------------------------------------

  send(data: unknown): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data));
    }
  }

  // ---------------------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------------------

  onMessage<T>(type: string, handler: MessageHandler<T>): () => void {
    const existing = this.handlers.get(type) ?? [];
    existing.push(handler as MessageHandler);
    this.handlers.set(type, existing);

    // Return un-subscribe function
    return () => {
      const current = this.handlers.get(type) ?? [];
      this.handlers.set(
        type,
        current.filter((h) => h !== handler),
      );
    };
  }

  /** Subscribe to all incoming messages (raw parsed JSON). */
  onAnyMessage(handler: MessageHandler): () => void {
    return this.onMessage('__message', handler);
  }

  onOpen(handler: () => void): () => void {
    return this.onMessage('__open', handler);
  }

  onClose(handler: (event: CloseEvent) => void): () => void {
    return this.onMessage('__close', handler as MessageHandler);
  }

  onError(handler: () => void): () => void {
    return this.onMessage('__error', handler);
  }

  onMaxRetries(handler: () => void): () => void {
    return this.onMessage('__max_retries', handler);
  }

  private _emit(type: string, data: unknown): void {
    const handlers = this.handlers.get(type) ?? [];
    for (const h of handlers) {
      try {
        h(data);
      } catch {
        // Don't let one handler error kill others
      }
    }
  }

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  get readyState(): number {
    return this.socket?.readyState ?? WebSocket.CLOSED;
  }
}

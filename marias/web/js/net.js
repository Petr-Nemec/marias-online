// WebSocket connection with automatic reconnect and a keep-alive ping.

const PING_MS = 25000;
const MAX_BACKOFF_MS = 15000;

export class Net {
  /**
   * @param {object} handlers
   * @param {() => object} handlers.hello   builds the first message
   * @param {(message: object) => void} handlers.message
   * @param {(status: 'connecting'|'online'|'offline'|'stopped') => void} handlers.status
   */
  constructor(handlers) {
    this.handlers = handlers;
    this.socket = null;
    this.attempt = 0;
    this.stopped = true;
    this.retryTimer = 0;
    this.pingTimer = 0;
  }

  start() {
    this.stopped = false;
    this.attempt = 0;
    this.#open();
  }

  stop() {
    this.stopped = true;
    clearTimeout(this.retryTimer);
    clearInterval(this.pingTimer);
    if (this.socket) this.socket.close(1000);
    this.socket = null;
    this.handlers.status('stopped');
  }

  send(message) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
      return true;
    }
    return false;
  }

  #open() {
    clearTimeout(this.retryTimer);
    this.handlers.status(this.attempt === 0 ? 'connecting' : 'offline');
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${scheme}://${location.host}/ws`);
    this.socket = socket;

    socket.addEventListener('open', () => {
      if (this.socket !== socket) return;
      this.attempt = 0;
      socket.send(JSON.stringify(this.handlers.hello()));
      clearInterval(this.pingTimer);
      this.pingTimer = setInterval(() => this.send({ type: 'ping' }), PING_MS);
      this.handlers.status('online');
    });

    socket.addEventListener('message', (event) => {
      if (this.socket !== socket || typeof event.data !== 'string') return;
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      this.handlers.message(message);
    });

    socket.addEventListener('close', () => {
      if (this.socket !== socket) return;
      clearInterval(this.pingTimer);
      this.socket = null;
      if (this.stopped) return;
      this.attempt += 1;
      const backoff = Math.min(MAX_BACKOFF_MS, 500 * 2 ** Math.min(this.attempt, 5));
      this.handlers.status('offline');
      this.retryTimer = setTimeout(() => this.#open(), backoff * (0.7 + Math.random() * 0.6));
    });
  }
}

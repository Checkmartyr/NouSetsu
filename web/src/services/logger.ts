import { API_BASE } from './apiBase';

export interface FrontendLogEntry {
  timestamp?: string;
  level?: string;
  source?: string;
  message: string;
  stack?: string;
}

const BUFFER_MAX_SIZE = 50;
const FLUSH_INTERVAL_MS = 2500;

let logBuffer: FrontendLogEntry[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;
let isFlushing = false;
let isInitialized = false;

function formatTimestamp(): string {
  const now = new Date();
  return now.toISOString().replace('T', ' ').replace('Z', '');
}

export function logFrontend(
  level: 'INFO' | 'WARN' | 'ERROR',
  message: string,
  stack?: string,
  source = 'ui'
): void {
  const entry: FrontendLogEntry = {
    timestamp: formatTimestamp(),
    level,
    source,
    message,
    stack,
  };

  logBuffer.push(entry);

  if (logBuffer.length >= BUFFER_MAX_SIZE || level === 'ERROR') {
    void flushFrontendLogs();
  } else if (!flushTimer) {
    flushTimer = setTimeout(() => {
      flushTimer = null;
      void flushFrontendLogs();
    }, FLUSH_INTERVAL_MS);
  }
}

export async function flushFrontendLogs(): Promise<void> {
  if (isFlushing || logBuffer.length === 0) return;

  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }

  isFlushing = true;
  const itemsToSend = [...logBuffer];
  logBuffer = [];

  try {
    const url = `${API_BASE}/api/logs/frontend`;
    await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ logs: itemsToSend }),
    });
  } catch {
    // If backend is unreachable or restarting, prepend unsent items (up to buffer limit)
    // to preserve recent errors without creating recursive loops.
    logBuffer = [...itemsToSend.slice(-20), ...logBuffer].slice(-BUFFER_MAX_SIZE);
  } finally {
    isFlushing = false;
  }
}

export function initFrontendLogger(): void {
  if (isInitialized || typeof window === 'undefined') return;
  isInitialized = true;

  // Intercept window global errors
  window.addEventListener('error', (event: ErrorEvent) => {
    const msg = event.message || 'Unknown runtime error';
    const stack = event.error?.stack || `${event.filename}:${event.lineno}:${event.colno}`;
    logFrontend('ERROR', msg, stack, 'window.error');
  });

  // Intercept unhandled promise rejections
  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    let msg = 'Unhandled promise rejection';
    let stack: string | undefined;

    if (event.reason instanceof Error) {
      msg = event.reason.message || msg;
      stack = event.reason.stack;
    } else if (typeof event.reason === 'string') {
      msg = event.reason;
    } else {
      try {
        msg = JSON.stringify(event.reason);
      } catch {
        msg = String(event.reason);
      }
    }

    logFrontend('ERROR', msg, stack, 'unhandledrejection');
  });

  // Wrap console.error and console.warn while preserving native output
  const originalError = console.error;
  const originalWarn = console.warn;

  console.error = (...args: unknown[]) => {
    try {
      if (!isFlushing) {
        const msg = args
          .map((arg) => (arg instanceof Error ? arg.message : typeof arg === 'object' ? JSON.stringify(arg) : String(arg)))
          .join(' ');
        const errorArg = args.find((arg) => arg instanceof Error) as Error | undefined;
        logFrontend('ERROR', msg, errorArg?.stack, 'console.error');
      }
    } catch {
      // Fallback silently if serialization fails
    }
    originalError.apply(console, args);
  };

  console.warn = (...args: unknown[]) => {
    try {
      if (!isFlushing) {
        const msg = args
          .map((arg) => (arg instanceof Error ? arg.message : typeof arg === 'object' ? JSON.stringify(arg) : String(arg)))
          .join(' ');
        logFrontend('WARN', msg, undefined, 'console.warn');
      }
    } catch {
      // Fallback silently
    }
    originalWarn.apply(console, args);
  };

  // Flush remaining logs on page unload
  window.addEventListener('beforeunload', () => {
    if (logBuffer.length > 0 && navigator.sendBeacon) {
      const url = `${API_BASE}/api/logs/frontend`;
      const blob = new Blob([JSON.stringify({ logs: logBuffer })], { type: 'application/json' });
      navigator.sendBeacon(url, blob);
    }
  });

  logFrontend('INFO', 'NouSetsu frontend logger initialized', undefined, 'lifecycle');
}

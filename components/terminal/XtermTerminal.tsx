'use client';

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react';
import 'xterm/css/xterm.css';
import { useTerminalTheme } from '../TerminalThemeContext';

export type TerminalConnectionState = 'connected' | 'connecting' | 'reconnecting' | 'disconnected';

export interface XtermTerminalHandle {
  reconnect: () => void;
  clear: () => void;
  kill: () => void;
  copySelection: () => Promise<void>;
  selectAll: () => void;
  write: (value: string) => void;
  sendInput: (value: string) => void;
  getStatus: () => TerminalConnectionState;
}

interface XtermTerminalProps {
  wsUrl: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onStatusChange?: (status: TerminalConnectionState) => void;
  autoReconnect?: boolean;
  forceTheme?: 'dark' | 'light';
}

export const XtermTerminal = forwardRef<XtermTerminalHandle, XtermTerminalProps>(function XtermTerminal(
  { wsUrl, onConnect, onDisconnect, onStatusChange, autoReconnect = true, forceTheme },
  ref
) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const { theme } = useTerminalTheme();
  const terminalTheme = forceTheme ?? theme;
  const terminalInstanceRef = useRef<{ writeln: (value: string) => void; write: (value: string) => void; clear: () => void; selectAll: () => void; getSelection: () => string; dispose: () => void } | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const resizeHandlerRef = useRef<(() => void) | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const retryCountRef = useRef(0);
  const disposedRef = useRef(false);
  const callbacksRef = useRef({ onConnect, onDisconnect, onStatusChange });
  const [status, setStatus] = useState<TerminalConnectionState>('connecting');

  useEffect(() => {
    callbacksRef.current = { onConnect, onDisconnect, onStatusChange };
  }, [onConnect, onDisconnect, onStatusChange]);

  const emitStatus = useCallback((nextStatus: TerminalConnectionState) => {
    setStatus(nextStatus);
    callbacksRef.current.onStatusChange?.(nextStatus);
  }, []);

  const disconnectSocket = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.onopen = null;
      socketRef.current.onmessage = null;
      socketRef.current.onerror = null;
      socketRef.current.onclose = null;
      socketRef.current.close();
      socketRef.current = null;
    }
  }, []);

  const connectSocket = useCallback(async () => {
    if (!terminalRef.current) {
      return;
    }

    emitStatus(retryCountRef.current > 0 ? 'reconnecting' : 'connecting');
    disconnectSocket();

    const [{ Terminal }, { FitAddon }] = await Promise.all([
      import('xterm'),
      import('xterm-addon-fit'),
    ]);

    if (disposedRef.current || !terminalRef.current) {
      return;
    }

    if (!terminalInstanceRef.current) {
      const terminal = new Terminal({
        cursorBlink: true,
        fontFamily: "'JetBrains Mono', 'IBM Plex Mono', monospace",
        fontSize: 13,
        theme: {
          background: terminalTheme === 'dark' ? '#000000' : '#ffffff',
          foreground: terminalTheme === 'dark' ? '#e2e8f0' : '#0f172a',
          cursor: '#00e5ff',
          selectionBackground: terminalTheme === 'dark' ? 'rgba(0, 229, 255, 0.22)' : 'rgba(0, 229, 255, 0.18)',
        },
      });

      const fitAddon = new FitAddon();
      terminal.loadAddon(fitAddon);
      terminal.open(terminalRef.current);
      fitAddon.fit();

      resizeHandlerRef.current = () => fitAddon.fit();
      window.addEventListener('resize', resizeHandlerRef.current);

      terminal.onData((data) => {
        if (socketRef.current?.readyState === WebSocket.OPEN) {
          socketRef.current.send(data);
        }
      });

      terminalInstanceRef.current = {
        writeln: terminal.writeln.bind(terminal),
        write: terminal.write.bind(terminal),
        clear: terminal.clear.bind(terminal),
        selectAll: terminal.selectAll.bind(terminal),
        getSelection: terminal.getSelection.bind(terminal),
        dispose: terminal.dispose.bind(terminal),
      };
    }

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      retryCountRef.current = 0;
      emitStatus('connected');
      callbacksRef.current.onConnect?.();
      terminalInstanceRef.current?.writeln('\x1b[36mConnected to NEUROS PTY Backend...\x1b[0m');
    };

    ws.onmessage = (event) => {
      terminalInstanceRef.current?.write(event.data);
    };

    ws.onerror = () => {
      emitStatus('reconnecting');
    };

    ws.onclose = () => {
      callbacksRef.current.onDisconnect?.();
      terminalInstanceRef.current?.writeln('\r\n\x1b[31mDisconnected from PTY Backend.\x1b[0m');
      if (!disposedRef.current) {
        if (!autoReconnect) {
          emitStatus('disconnected');
          return;
        }

        if (reconnectTimerRef.current) {
          window.clearTimeout(reconnectTimerRef.current);
        }

        const delay = Math.min(10000, 1000 * Math.max(1, retryCountRef.current + 1));
        retryCountRef.current += 1;
        emitStatus('reconnecting');
        terminalInstanceRef.current?.writeln(`\r\n\x1b[33mConnection lost. Retrying in ${Math.ceil(delay / 1000)}s...\x1b[0m`);
        reconnectTimerRef.current = window.setTimeout(() => {
          void connectSocket();
        }, delay);
      }
    };
  }, [autoReconnect, disconnectSocket, emitStatus, terminalTheme, wsUrl]);

  useEffect(() => {
    disposedRef.current = false;
    void connectSocket();

    return () => {
      disposedRef.current = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (resizeHandlerRef.current) {
        window.removeEventListener('resize', resizeHandlerRef.current);
      }
      disconnectSocket();
      terminalInstanceRef.current?.dispose();
      terminalInstanceRef.current = null;
    };
  }, [connectSocket, disconnectSocket]);

  useImperativeHandle(ref, () => ({
    reconnect: () => {
      retryCountRef.current = 0;
      void connectSocket();
    },
    clear: () => {
      terminalInstanceRef.current?.clear();
    },
    kill: () => {
      retryCountRef.current = 0;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      disconnectSocket();
      emitStatus('disconnected');
      callbacksRef.current.onDisconnect?.();
    },
    copySelection: async () => {
      const selection = terminalInstanceRef.current?.getSelection() ?? '';
      if (selection) {
        await navigator.clipboard.writeText(selection);
      }
    },
    selectAll: () => {
      terminalInstanceRef.current?.selectAll();
    },
    write: (value: string) => {
      terminalInstanceRef.current?.write(value);
    },
    sendInput: (value: string) => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(value);
      }
    },
    getStatus: () => status,
  }), [connectSocket, disconnectSocket, emitStatus, status]);

  return <div ref={terminalRef} className="h-full w-full" />;
});

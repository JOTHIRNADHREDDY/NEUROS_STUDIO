import { useEffect, useRef } from 'react';
import { useGlobalState } from '../stores/useGlobalState';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws';

export function useBackend() {
  const ws = useRef<WebSocket | null>(null);
  const { updateFromBackend } = useGlobalState();

  useEffect(() => {
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      console.log('Connected to NEUROS Backend WS');
    };

    ws.current.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'state_update') {
          updateFromBackend(message.data);
        } else if (message.type === 'event') {
          // Handle events like terminal logs, notifications
          console.log('Received event from backend:', message);
        }
      } catch (err) {
        console.error('Failed to parse WS message:', err);
      }
    };

    ws.current.onclose = () => {
      console.log('Disconnected from NEUROS Backend WS');
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [updateFromBackend]);

  const sendCommand = (type: string, payload: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type, payload }));
    }
  };

  return { sendCommand };
}

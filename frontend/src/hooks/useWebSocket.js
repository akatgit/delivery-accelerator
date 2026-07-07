import { useEffect, useRef } from "react";
import { streamUrl } from "../api/client";

// Connects to /api/sessions/{id}/stream (ARCHITECTURE_v2.0.md section 10.2)
// and calls onMessage with each parsed JSON frame. onMessage is read from a
// ref rather than a hook dependency so callers can pass an inline callback
// without forcing a reconnect on every render.
export function useWebSocket(sessionId, onMessage) {
  const socketRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!sessionId) return undefined;

    const socket = new WebSocket(streamUrl(sessionId));
    socketRef.current = socket;

    socket.onmessage = (event) => {
      try {
        onMessageRef.current(JSON.parse(event.data));
      } catch {
        // ignore malformed frames
      }
    };

    return () => {
      socket.close();
      socketRef.current = null;
    };
  }, [sessionId]);

  return socketRef;
}

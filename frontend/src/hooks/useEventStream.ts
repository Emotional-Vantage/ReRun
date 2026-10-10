import { useEffect, useRef, useState } from 'react';
import type { Event } from '../api/types';

export interface UseEventStreamOptions {
  projectId: string | null;
  onEvent?: (event: Event) => void;
  onError?: (err: any) => void;
}

export function useEventStream({ projectId, onEvent, onError }: UseEventStreamOptions) {
  const [events, setEvents] = useState<Event[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connected' | 'reconnecting' | 'offline'>('idle');
  const lastEventIdRef = useRef<number>(0);
  const esRef = useRef<EventSource | null>(null);

  // Keep the latest callbacks in refs so the effect does not need them as dependencies,
  // and so a reconnect never invokes a stale closure.
  const onEventRef = useRef(onEvent);
  const onErrorRef = useRef(onError);
  onEventRef.current = onEvent;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!projectId) {
      setConnectionStatus('idle');
      return;
    }

    lastEventIdRef.current = 0;
    let isFirstConnect = true;
    let cancelled = false;

    setConnectionStatus('reconnecting');
    let reconnectTimeout: any = null;

    function connect() {
      if (cancelled) return;
      if (esRef.current) {
        esRef.current.close();
      }

      const resumeId = isFirstConnect ? 0 : lastEventIdRef.current;
      isFirstConnect = false;

      const url = `/api/projects/${projectId}/events?last_event_id=${resumeId}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        setConnectionStatus('connected');
      };

      es.onmessage = (msgEvent) => {
        try {
          const data: Event = JSON.parse(msgEvent.data);
          if (data && data.id) {
            lastEventIdRef.current = Math.max(lastEventIdRef.current, data.id);
            setEvents((prev) => {
              if (prev.some((e) => e.id === data.id)) return prev;
              return [...prev, data];
            });
            onEventRef.current?.(data);
          }
        } catch (e) {
          console.error('Failed to parse SSE event data', e);
        }
      };

      es.onerror = (err) => {
        setConnectionStatus('reconnecting');
        onErrorRef.current?.(err);
        es.close();
        reconnectTimeout = setTimeout(connect, 3000);
      };
    }

    connect();

    return () => {
      cancelled = true;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [projectId]);

  return { events, connectionStatus };
}

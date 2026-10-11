import { useEffect, useRef, useState } from 'react';
import { pollEvents } from '../api/client';
import type { Event } from '../api/types';

export interface UseEventStreamOptions {
  projectId: string | null;
  onEvent?: (event: Event) => void;
  onError?: (err: any) => void;
}

export type ConnectionStatus = 'idle' | 'connected' | 'reconnecting' | 'polling' | 'offline';

/**
 * How long a stream may stay open without delivering anything before we stop
 * believing in it.
 *
 * On a healthy connection the server replays the project's whole event history
 * the moment the stream opens, so the first message lands in milliseconds --
 * even for a finished project. Silence past this point means the bytes are
 * being held somewhere between the server and here.
 */
const SILENT_STREAM_MS = 5000;
const POLL_INTERVAL_MS = 2000;

export function useEventStream({ projectId, onEvent, onError }: UseEventStreamOptions) {
  const [events, setEvents] = useState<Event[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('idle');
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
    let reconnectTimeout: any = null;
    let silenceTimer: any = null;
    let pollTimer: any = null;
    let polling = false;

    setConnectionStatus('reconnecting');

    const ingest = (data: Event) => {
      if (!data || !data.id) return;
      lastEventIdRef.current = Math.max(lastEventIdRef.current, data.id);
      setEvents((prev) => {
        if (prev.some((e) => e.id === data.id)) return prev;
        return [...prev, data];
      });
      onEventRef.current?.(data);
    };

    /*
      Fall back to ordinary requests when the stream cannot reach us.

      Server-sent events need every hop in between to forward a response body
      before that body has finished, and not everything does. A Cloudflare
      quick tunnel holds the body until the response completes; because an
      event stream never completes, the dashboard received the 200 and the
      content-type and then nothing at all, leaving the trace ledger empty on a
      run that had already finished. Response headers do not fix it --
      no-transform and identity encoding were both honoured and changed
      nothing.

      So the stream is treated as an optimisation rather than a requirement.
      Polling returns the same rows from the same table, a second or two later,
      and `last_event_id` means each request carries only what is new.
    */
    const startPolling = (reason: string) => {
      if (cancelled || polling) return;
      polling = true;
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (silenceTimer) clearTimeout(silenceTimer);
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      setConnectionStatus('polling');
      // eslint-disable-next-line no-console
      console.info(`[rerun] live stream unavailable (${reason}); polling for events instead.`);

      const tick = async () => {
        if (cancelled) return;
        try {
          const res = await pollEvents(projectId, lastEventIdRef.current);
          res.events.forEach(ingest);
          setConnectionStatus('polling');
        } catch (e) {
          setConnectionStatus('offline');
          onErrorRef.current?.(e);
        }
      };
      void tick();
      pollTimer = setInterval(tick, POLL_INTERVAL_MS);
    };

    function connect() {
      if (cancelled || polling) return;
      if (esRef.current) esRef.current.close();

      const resumeId = isFirstConnect ? 0 : lastEventIdRef.current;
      isFirstConnect = false;

      const url = `/api/projects/${projectId}/events?last_event_id=${resumeId}`;
      const es = new EventSource(url);
      esRef.current = es;

      // Armed on every attempt, not just the first: a proxy that buffers will
      // happily complete the handshake each time and then stay silent, so
      // `onopen` alone is not evidence that anything is getting through.
      if (silenceTimer) clearTimeout(silenceTimer);
      silenceTimer = setTimeout(() => startPolling('no events received'), SILENT_STREAM_MS);

      es.onopen = () => {
        if (!polling) setConnectionStatus('connected');
      };

      es.onmessage = (msgEvent) => {
        if (silenceTimer) {
          clearTimeout(silenceTimer);
          silenceTimer = null;
        }
        if (!polling) setConnectionStatus('connected');
        try {
          ingest(JSON.parse(msgEvent.data) as Event);
        } catch (e) {
          console.error('Failed to parse SSE event data', e);
        }
      };

      es.onerror = (err) => {
        if (polling) return;
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
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (silenceTimer) clearTimeout(silenceTimer);
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [projectId]);

  return { events, connectionStatus };
}

import React, { useEffect, useRef, useState } from 'react';
import { ScrollText, Pause, Play } from 'lucide-react';
import { fetchRunLog } from '../../api/client';

interface TerminalProps {
  projectId: string;
  totalAttempts: number;
  currentLogText?: string;
}

export const Terminal: React.FC<TerminalProps> = ({
  projectId,
  totalAttempts,
  currentLogText = '',
}) => {
  const [selectedRun, setSelectedRun] = useState<number>(totalAttempts || 1);
  const [logContent, setLogContent] = useState<string>(currentLogText);
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const terminalEndRef = useRef<HTMLDivElement>(null);

  // Update selected run when totalAttempts increments
  useEffect(() => {
    if (totalAttempts > 0) {
      setSelectedRun(totalAttempts);
    }
  }, [totalAttempts]);

  // Load log when selected run changes or when currentLogText updates
  useEffect(() => {
    if (selectedRun === totalAttempts && currentLogText) {
      setLogContent(currentLogText);
    } else if (projectId && selectedRun > 0) {
      fetchRunLog(projectId, selectedRun)
        .then((log) => setLogContent(log || ''))
        .catch(() => setLogContent(''));
    }
  }, [projectId, selectedRun, totalAttempts, currentLogText]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logContent, autoScroll]);

  // Live elapsed timer
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatElapsed = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const runsList = Array.from({ length: Math.max(1, totalAttempts) }, (_, i) => i + 1);

  const lines = logContent ? logContent.split('\n') : [];

  /*
    This panel used to be a black terminal with teal and slate accents, dropped
    into the middle of a page made of paper and ink. It was the one surface that
    looked borrowed from another product. Nothing about a container log requires
    a dark chrome -- it is a printed record of what the machine did, so it is
    now set as one: a run sheet on paper, ruled, with the line numbers in the
    margin. The content, the colouring of error lines and every control are
    unchanged; only the surface is.
  */
  return (
    <div className="flex flex-col h-full min-h-0 bg-paper border border-kraft rounded-sm overflow-hidden shadow-sm font-mono text-xs">
      {/* Header controls: single centered row */}
      <div className="shrink-0 flex items-center justify-center flex-wrap gap-2 px-3 py-2 bg-kraft-light border-b border-kraft text-center">
        <ScrollText className="w-4 h-4 text-rust shrink-0" />
        <span className="font-bold text-ink uppercase tracking-[0.14em] text-[11px] shrink-0">
          Run Log
        </span>
        <span
          className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-paper border border-kraft text-ink-soft text-[11px] shrink-0"
          title="Live session elapsed time"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse inline-block" />
          <span>{formatElapsed(elapsedSeconds)}</span>
        </span>
        <select
          value={selectedRun}
          onChange={(e) => setSelectedRun(Number(e.target.value))}
          className="bg-paper text-ink border border-kraft rounded-sm px-2 py-0.5 text-xs focus:outline-none focus:border-rust shrink-0 cursor-pointer"
        >
          {runsList.map((r) => (
            <option key={r} value={r}>
              Run #{r}
            </option>
          ))}
        </select>
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-sm border text-[11px] transition-colors shrink-0 ${
            autoScroll
              ? 'bg-paper text-rust-ink border-rust/50 font-semibold'
              : 'bg-paper text-ink-soft border-kraft'
          }`}
          title={autoScroll ? 'Pause autoscroll' : 'Resume autoscroll'}
        >
          {autoScroll ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
          <span>{autoScroll ? 'Following' : 'Paused'}</span>
        </button>
      </div>

      {/* Log sheet */}
      <div className="flex-1 min-h-0 overflow-y-auto bg-paper selection:bg-rust/20">
        {!logContent ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-ink-soft px-6">
            <ScrollText className="w-8 h-8 mb-2 opacity-25 text-rust" />
            <p>Nothing has run yet. Output from the container will be written here.</p>
          </div>
        ) : (
          <div className="py-2">
            {lines.map((line, idx) => {
              const isError =
                line.toLowerCase().includes('error') ||
                line.toLowerCase().includes('exception') ||
                line.toLowerCase().includes('traceback');

              return (
                <div
                  key={idx}
                  className={`flex items-start gap-3 px-3 leading-relaxed ${
                    isError ? 'bg-[#F6E2DC]' : ''
                  }`}
                >
                  {/* Ruled margin, as on a numbered printout. */}
                  <span
                    className="shrink-0 w-9 text-right tabular-nums text-[10px] pt-[1px] text-ink-soft/45 select-none border-r border-kraft/60 pr-2"
                    aria-hidden="true"
                  >
                    {idx + 1}
                  </span>
                  <span
                    className={`whitespace-pre-wrap break-all ${
                      isError ? 'text-rust-ink font-semibold' : 'text-ink'
                    }`}
                  >
                    {line}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
};

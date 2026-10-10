import React, { useEffect, useRef, useState } from 'react';
import { Terminal as TerminalIcon, Download, Pause, Play } from 'lucide-react';
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

  const handleDownloadLog = () => {
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `run_${selectedRun}.log`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const runsList = Array.from({ length: Math.max(1, totalAttempts) }, (_, i) => i + 1);

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#0B1120] border border-[#CDC5B4] rounded-xl overflow-hidden shadow-sm font-mono text-xs">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 bg-[#141C2B] border-b border-[#2A3853]">
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-4 h-4 text-teal-400" />
          <span className="font-semibold text-[#F1ECE0] uppercase tracking-wider text-[11px]">
            Sandbox Container Console
          </span>
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#1E293B] border border-[#334155] text-amber-300 font-mono text-[11px]" title="Live session elapsed time">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
            <span>⏱️ {formatElapsed(elapsedSeconds)}</span>
          </span>
          <select
            value={selectedRun}
            onChange={(e) => setSelectedRun(Number(e.target.value))}
            className="ml-2 bg-[#1E293B] text-[#F1ECE0] border border-[#334155] rounded px-2 py-0.5 text-xs focus:outline-none focus:border-teal-400"
          >
            {runsList.map((r) => (
              <option key={r} value={r}>
                Run #{r}
              </option>
            ))}
          </select>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] transition-colors ${
              autoScroll
                ? 'bg-[#1E293B] text-teal-300 border-teal-500/40 font-medium'
                : 'bg-[#1E293B] text-[#94A3B8] border-[#334155]'
            }`}
            title={autoScroll ? 'Pause autoscroll' : 'Resume autoscroll'}
          >
            {autoScroll ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
            <span className="hidden sm:inline">{autoScroll ? 'Auto-scroll on' : 'Paused'}</span>
          </button>

          <button
            onClick={handleDownloadLog}
            disabled={!logContent}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-[#1E293B] hover:bg-[#334155] text-[#F1ECE0] border border-[#334155] text-[11px] disabled:opacity-40 transition-colors"
            title="Download log file"
          >
            <Download className="w-3 h-3" />
            <span className="hidden sm:inline">Download</span>
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div className="flex-1 min-h-0 p-4 overflow-y-auto bg-[#060B14] text-[#CBD5E1] space-y-0.5 leading-relaxed selection:bg-teal-500/30">
        {!logContent ? (
          <div className="h-full flex flex-col items-center justify-center text-center text-[#64748B]">
            <TerminalIcon className="w-8 h-8 mb-2 opacity-30 text-teal-400" />
            <p>No run has started yet. Live output will stream here.</p>
          </div>
        ) : (
          logContent.split('\n').map((line, idx) => {
            const isError =
              line.toLowerCase().includes('error') ||
              line.toLowerCase().includes('exception') ||
              line.toLowerCase().includes('traceback');

            return (
              <div
                key={idx}
                className={`whitespace-pre-wrap break-all ${
                  isError ? 'text-red-400 bg-red-950/20 px-1 rounded' : 'text-slate-300'
                }`}
              >
                {line}
              </div>
            );
          })
        )}
        <div ref={terminalEndRef} />
      </div>
    </div>
  );
};

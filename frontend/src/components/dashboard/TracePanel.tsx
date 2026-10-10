import React, { useEffect, useRef } from 'react';
import type { Event } from '../../api/types';
import { TraceRow } from './TraceRow';
import { Activity } from 'lucide-react';

interface TracePanelProps {
  events: Event[];
  onSelectEvidence?: (id: string) => void;
}

export const TracePanel: React.FC<TracePanelProps> = ({ events, onSelectEvidence }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl overflow-hidden shadow-sm">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-3 bg-[#F4F1E8] border-b border-[#CDC5B4]">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-rust" />
          <h3 className="text-xs font-semibold text-[#1F2A44] uppercase tracking-wider font-mono">
            Execution Trace Ledger
          </h3>
        </div>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#E5DFD3] text-[#4A5470] border border-[#CDC5B4]">
          {events.length} events
        </span>
      </div>

      {/* Events List */}
      <div ref={scrollRef} className="flex-1 min-h-0 p-4 overflow-y-auto space-y-2.5">
        {events.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-[#4A5470] font-mono text-xs">
            <Activity className="w-8 h-8 mb-2 text-rust opacity-40 animate-pulse" />
            <p className="max-w-[200px] leading-relaxed">
              Waiting for the first step. Rerun will record every decision here.
            </p>
          </div>
        ) : (
          events.map((evt) => (
            <TraceRow key={evt.id} event={evt} onSelectEvidence={onSelectEvidence} />
          ))
        )}
      </div>
    </div>
  );
};

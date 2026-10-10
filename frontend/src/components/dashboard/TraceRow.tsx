import React from 'react';
import type { Event } from '../../api/types';
import { EvidenceChip } from '../ui/EvidenceChip';

interface TraceRowProps {
  event: Event;
  onSelectEvidence?: (id: string) => void;
}

export const TraceRow: React.FC<TraceRowProps> = ({ event, onSelectEvidence }) => {
  const roleStyles = {
    solver: 'bg-teal-50 text-teal-800 border-teal-300 font-bold',
    critic: 'bg-purple-50 text-purple-800 border-purple-300 font-bold',
    human: 'bg-amber-50 text-amber-900 border-amber-400 font-bold',
    arbiter: 'bg-[#E5DFD3] text-[#1F2A44] border-[#CDC5B4]',
    tool: 'bg-[#FAF7F0] text-[#4A5470] border-[#CDC5B4]',
    system: 'bg-[#FAF7F0] text-[#4A5470] border-[#CDC5B4]',
  }[event.role] || 'bg-[#FAF7F0] text-[#4A5470] border-[#CDC5B4]';

  // Check if this is the highlighted "pivotal moment"
  const isPivotal =
    event.summary.toLowerCase().includes('outside tolerance') ||
    event.summary.toLowerCase().includes('compare_configuration') ||
    event.summary.toLowerCase().includes('silent divergence') ||
    event.type === 'orchestrator_forced';

  return (
    <div
      className={`p-3 rounded-lg border text-xs font-mono transition-all ${
        isPivotal
          ? 'bg-[#FEF3C7] border-2 border-amber-600/70 shadow-sm text-[#1F2A44]'
          : 'bg-[#FAF7F0] border border-[#CDC5B4] hover:bg-[#F4F1E8] text-[#1F2A44]'
      }`}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2">
          {/* Role badge */}
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${roleStyles}`}>
            {event.role}
          </span>
          {event.tool && (
            <span className="px-1.5 py-0.5 rounded bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] text-[10px] font-medium">
              {event.tool}
            </span>
          )}
          <span className="text-[#4A5470] text-[10px]">Step {event.step}</span>
        </div>

        <span className="text-[#4A5470] text-[10px]">
          {event.ts ? new Date(event.ts).toLocaleTimeString() : ''}
        </span>
      </div>

      {/* Summary message */}
      <div className={`leading-relaxed text-[#1F2A44] ${isPivotal ? 'font-semibold text-amber-900' : ''}`}>
        {event.summary}
      </div>

      {/* Evidence references */}
      {event.evidence_ids && event.evidence_ids.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 pt-1.5 border-t border-[#CDC5B4]/50">
          <span className="text-[10px] text-[#4A5470]">Evidence:</span>
          {event.evidence_ids.map((eid) => (
            <EvidenceChip key={eid} id={eid} onClick={onSelectEvidence} />
          ))}
        </div>
      )}
    </div>
  );
};

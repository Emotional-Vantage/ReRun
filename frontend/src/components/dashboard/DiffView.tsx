import React, { useState } from 'react';
import { GitCommit, FileCode } from 'lucide-react';
import type { Patch } from '../../api/types';

interface DiffViewProps {
  patch?: Patch | null;
}

export const DiffView: React.FC<DiffViewProps> = ({ patch }) => {
  const [activeFileTab, setActiveFileTab] = useState<number>(0);

  if (!patch) {
    return (
      <div className="flex flex-col h-full min-h-0 bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl overflow-hidden shadow-sm p-6 items-center justify-center text-center text-[#4A5470] font-mono text-xs">
        <GitCommit className="w-8 h-8 mb-2 text-rust opacity-40 animate-pulse" />
        <p className="max-w-[220px] leading-relaxed">
          No patch yet. Proposed changes appear here after diagnosis.
        </p>
      </div>
    );
  }

  // Parse diff files if unified diff string or edits array
  const files = patch.edits?.length
    ? patch.edits.map((e) => e.file)
    : ['patch.diff'];

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl overflow-hidden shadow-sm font-mono text-xs text-[#1F2A44]">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between px-4 py-2.5 bg-[#F4F1E8] border-b border-[#CDC5B4]">
        <div className="flex items-center gap-2">
          <GitCommit className="w-4 h-4 text-rust" />
          <span className="font-semibold text-[#1F2A44] uppercase tracking-wider text-[11px]">
            {patch.id || 'Proposed Patch'}
          </span>
          <span className="px-2 py-0.5 rounded bg-[#FAF7F0] text-rust border border-[#CDC5B4] text-[10px] font-bold">
            {patch.risk_class || 'fix'}
          </span>
        </div>

        <span className="text-[11px] text-[#4A5470]">
          Status: <span className="text-rust font-bold capitalize">{patch.status || 'proposed'}</span>
        </span>
      </div>

      {/* File Tabs */}
      {files.length > 1 && (
        <div className="shrink-0 flex border-b border-[#CDC5B4] bg-[#E5DFD3] px-2 overflow-x-auto">
          {files.map((file, idx) => (
            <button
              key={file}
              onClick={() => setActiveFileTab(idx)}
              className={`flex items-center gap-1.5 px-3 py-1.5 border-b-2 text-xs transition-colors ${
                activeFileTab === idx
                  ? 'border-rust text-[#1F2A44] font-bold bg-[#FAF7F0]'
                  : 'border-transparent text-[#4A5470] hover:text-[#1F2A44]'
              }`}
            >
              <FileCode className="w-3.5 h-3.5" />
              <span>{file}</span>
            </button>
          ))}
        </div>
      )}

      {/* Diff Content */}
      <div className="flex-1 min-h-0 p-4 overflow-y-auto bg-[#FAF7F0] text-[#1F2A44] leading-relaxed space-y-0.5">
        {patch.rationale && (
          <div className="mb-3 p-2.5 rounded bg-[#F4F1E8] border border-[#CDC5B4] text-xs text-[#1F2A44]">
            <span className="text-rust font-bold">Rationale: </span>
            {patch.rationale}
          </div>
        )}

        {patch.diff ? (
          patch.diff.split('\n').map((line, idx) => {
            let lineClass = 'text-[#1F2A44]';
            if (line.startsWith('+')) {
              lineClass = 'text-[#15803D] bg-[#DCFCE7] px-1 rounded block font-medium';
            } else if (line.startsWith('-')) {
              lineClass = 'text-[#B91C1C] bg-[#FEE2E2] px-1 rounded block font-medium';
            } else if (line.startsWith('@@')) {
              lineClass = 'text-[#8F3F20] bg-[#FEF3C7] px-1 block font-bold';
            }

            return (
              <div key={idx} className={lineClass}>
                {line}
              </div>
            );
          })
        ) : (
          <div className="space-y-2">
            {patch.edits?.map((edit, idx) => (
              <div key={idx} className="p-2 rounded bg-[#F4F1E8] border border-[#CDC5B4] space-y-1">
                <div className="text-rust font-bold">{edit.file} ({edit.op})</div>
                {edit.old && (
                  <div className="text-[#B91C1C] bg-[#FEE2E2] px-1.5 py-0.5 rounded">- {edit.old}</div>
                )}
                {edit.new && (
                  <div className="text-[#15803D] bg-[#DCFCE7] px-1.5 py-0.5 rounded">+ {edit.new}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

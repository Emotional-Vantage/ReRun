import React from 'react';
import { Paperclip } from 'lucide-react';

interface EvidenceChipProps {
  id: string;
  onClick?: (id: string) => void;
  className?: string;
}

export const EvidenceChip: React.FC<EvidenceChipProps> = ({ id, onClick, className = '' }) => {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onClick?.(id);
      }}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono bg-[#FAF7F0] text-teal-800 border border-teal-400/50 hover:border-teal-600 hover:bg-teal-50 transition-all cursor-pointer font-bold shadow-sm ${className}`}
      title={`Click to view evidence ${id}`}
    >
      <Paperclip className="w-3 h-3 text-teal-700" />
      <span>{id}</span>
    </button>
  );
};

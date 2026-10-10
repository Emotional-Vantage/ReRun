import React, { useEffect, useState } from 'react';
import { X, Copy, Check, FileText, Hash } from 'lucide-react';
import type { EvidenceItem } from '../../api/types';
import { fetchEvidence } from '../../api/client';

interface EvidenceDrawerProps {
  projectId: string;
  evidenceId: string | null;
  onClose: () => void;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  projectId,
  evidenceId,
  onClose,
}) => {
  const [evidence, setEvidence] = useState<EvidenceItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedSha, setCopiedSha] = useState(false);

  useEffect(() => {
    if (!evidenceId) {
      setEvidence(null);
      return;
    }

    setLoading(true);
    setError(null);
    fetchEvidence(projectId, evidenceId)
      .then((data) => {
        setEvidence(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || 'Failed to load evidence');
        setLoading(false);
      });
  }, [projectId, evidenceId]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!evidenceId) return null;

  const copySha = () => {
    if (evidence?.sha256) {
      navigator.clipboard.writeText(evidence.sha256);
      setCopiedSha(true);
      setTimeout(() => setCopiedSha(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
      <div
        className="w-full max-w-xl h-full bg-[#FAF7F0] border-l border-[#CDC5B4] p-6 flex flex-col shadow-2xl overflow-y-auto text-[#1F2A44] font-mono text-xs"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-4 mb-4">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded bg-[#E5DFD3] text-teal-900 font-mono text-xs border border-[#CDC5B4] font-bold">
              {evidenceId}
            </span>
            <h2 className="text-base font-serif uppercase tracking-wide text-[#1F2A44] font-bold">
              Evidence Artifact Ledger
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#4A5470] hover:text-[#1F2A44] hover:bg-[#E5DFD3] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        {loading && (
          <div className="space-y-4 py-8">
            <div className="h-6 bg-[#E5DFD3] rounded animate-pulse w-3/4"></div>
            <div className="h-20 bg-[#E5DFD3] rounded animate-pulse"></div>
            <div className="h-40 bg-[#E5DFD3] rounded animate-pulse"></div>
          </div>
        )}

        {error && (
          <div className="p-4 rounded bg-red-50 border border-red-300 text-red-700 text-xs">
            {error}
          </div>
        )}

        {evidence && (
          <div className="space-y-6 flex-1 flex flex-col text-xs">
            {/* Metadata Card */}
            <div className="bg-[#F4F1E8] rounded-lg border border-[#CDC5B4] p-4 space-y-3 font-mono text-xs text-[#1F2A44]">
              <div className="flex items-start justify-between">
                <span className="text-[#4A5470]">Artifact Path:</span>
                <span className="text-[#1F2A44] text-right truncate max-w-[280px] font-semibold" title={evidence.artifact_path}>
                  {evidence.artifact_path}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[#4A5470]">Created By:</span>
                <span className="text-teal-800 font-bold">{evidence.created_by_tool}</span>
              </div>
              {evidence.line_start !== undefined && evidence.line_start !== null && (
                <div className="flex items-center justify-between">
                  <span className="text-[#4A5470]">Line Range:</span>
                  <span className="text-[#1F2A44] font-semibold">
                    L{evidence.line_start} - L{evidence.line_end || evidence.line_start}
                  </span>
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t border-[#CDC5B4]/60">
                <span className="text-[#4A5470] flex items-center gap-1">
                  <Hash className="w-3.5 h-3.5" /> SHA256:
                </span>
                <button
                  onClick={copySha}
                  className="flex items-center gap-1 text-[11px] text-[#1F2A44] hover:text-black bg-[#FAF7F0] px-2 py-0.5 rounded border border-[#CDC5B4] hover:bg-[#E5DFD3] transition-colors"
                  title="Click to copy SHA-256"
                >
                  <span className="truncate max-w-[140px] font-mono">{evidence.sha256}</span>
                  {copiedSha ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3 text-[#4A5470]" />}
                </button>
              </div>
            </div>

            {/* Excerpt Section */}
            <div className="flex-1 flex flex-col">
              <div className="flex items-center gap-1.5 text-xs font-mono text-[#4A5470] mb-2 uppercase tracking-wider font-bold">
                <FileText className="w-4 h-4 text-rust" />
                <span>Verified Content Excerpt</span>
              </div>
              <div className="flex-1 min-h-[200px] p-4 bg-[#FFFFFF] border border-[#CDC5B4] rounded-lg font-mono text-xs text-[#1F2A44] overflow-x-auto whitespace-pre-wrap leading-relaxed select-text shadow-sm">
                {evidence.excerpt}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

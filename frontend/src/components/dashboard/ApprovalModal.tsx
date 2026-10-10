import React, { useState } from 'react';
import { AlertTriangle, Check, X, FileEdit, Edit3, Scale } from 'lucide-react';
import type { Patch, CriticReview } from '../../api/types';
import { CriticPanel } from './CriticPanel';
import { EvidenceChip } from '../ui/EvidenceChip';

interface ApprovalModalProps {
  isOpen: boolean;
  approvalId: string;
  patch: Patch;
  criticReview?: CriticReview | null;
  banner?: string | null;
  requiresExtraConfirm?: boolean;
  onApprove: (comment?: string, confirmExtra?: boolean) => void;
  onReject: (comment?: string) => void;
  onEdit?: (edits: any[], comment?: string) => Promise<void>;
  onSelectEvidence?: (id: string) => void;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  isOpen,
  approvalId,
  patch,
  criticReview,
  banner,
  requiresExtraConfirm = false,
  onApprove,
  onReject,
  onEdit,
  onSelectEvidence,
}) => {
  const [comment, setComment] = useState('');
  const [extraConfirmed, setExtraConfirmed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Edit patch mode
  const [isEditing, setIsEditing] = useState(false);
  const [editsText, setEditsText] = useState(JSON.stringify(patch.edits || [], null, 2));
  const [editError, setEditError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isConfigAlignment = patch.risk_class === 'config_alignment';
  const hasBanner = Boolean(banner);
  const canApprove = !requiresExtraConfirm || extraConfirmed;

  const handleApprove = async () => {
    if (!canApprove || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onApprove(comment, extraConfirmed);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onReject(comment);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApplyEdit = async () => {
    if (!onEdit || isSubmitting) return;
    setEditError(null);
    let parsed: any;
    try {
      parsed = JSON.parse(editsText);
      if (!Array.isArray(parsed)) {
        throw new Error('Edits must be an array of edit operations');
      }
    } catch (e: any) {
      setEditError(`Invalid JSON: ${e.message}`);
      return;
    }

    setIsSubmitting(true);
    try {
      await onEdit(parsed, comment);
    } catch (e: any) {
      setEditError(e.message || 'Edit rejected by policy check');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 overflow-y-auto animate-fade-in">
      <div
        className="w-full max-w-3xl bg-[#FAF7F0] border-2 border-rust rounded-xl p-6 shadow-2xl space-y-6 max-h-[90vh] overflow-y-auto font-mono text-xs text-[#1F2A44]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-4">
          <div className="flex items-center gap-2.5">
            <span className="w-8 h-8 rounded bg-amber-100 border border-amber-300 flex items-center justify-center text-amber-800">
              <FileEdit className="w-4 h-4" />
            </span>
            <div>
              <h2 className="text-base font-serif uppercase tracking-wide text-[#1F2A44] font-bold">
                Human Approval Gate: {patch.id || 'Proposed Patch'}
              </h2>
              <span className="text-[11px] text-[#4A5470] font-mono">
                Action Required: Approval ID <span className="text-amber-800 font-bold">{approvalId}</span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] text-[10px] font-bold uppercase tracking-wider">
              {patch.risk_class}
            </span>
            {onEdit && (
              <button
                type="button"
                onClick={() => setIsEditing(!isEditing)}
                className={`flex items-center gap-1 px-2.5 py-1 rounded border text-[10px] font-bold uppercase tracking-wider transition-colors ${
                  isEditing
                    ? 'bg-amber-100 text-amber-900 border-amber-400'
                    : 'bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[#4A5470] border-[#CDC5B4]'
                }`}
              >
                <Edit3 className="w-3 h-3" />
                <span>{isEditing ? 'Cancel Edit' : 'Edit Patch'}</span>
              </button>
            )}
          </div>
        </div>

        {/* Warning Banner (if any) */}
        {hasBanner && (
          <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-300 flex items-start gap-3 text-amber-900">
            <AlertTriangle className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-amber-800 block">POLICY OR CRITIC WARNING:</span>
              <p className="text-[11px] leading-relaxed">
                Banner flagged: <span className="font-mono text-[#1F2A44] font-bold underline">{banner}</span>. Proceed with heightened scrutiny.
              </p>
            </div>
          </div>
        )}

        {/* Policy verdict */}
        {patch.policy_result && (
          <div
            className={`p-3.5 rounded-lg border space-y-2 text-[11px] ${
              patch.policy_result.passed
                ? 'bg-[#F4F1E8] border-[#CDC5B4] text-[#1F2A44]'
                : 'bg-red-50 border-red-300 text-red-900'
            }`}
          >
            <div className="flex items-center gap-2">
              <Scale className="w-4 h-4 shrink-0" />
              <span className="font-bold uppercase tracking-wider">
                Policy check (deterministic)
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                  patch.policy_result.passed
                    ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                    : 'bg-red-100 text-red-800 border border-red-300'
                }`}
              >
                {patch.policy_result.passed ? 'passed' : 'failed'}
              </span>
              {patch.policy_result.risk_class && (
                <span className="font-mono text-[10px] text-[#4A5470]">
                  {patch.policy_result.risk_class}
                </span>
              )}
            </div>

            {patch.policy_result.violations && patch.policy_result.violations.length > 0 && (
              <div>
                <span className="font-bold">Violations:</span>
                <ul className="list-disc list-inside leading-relaxed">
                  {patch.policy_result.violations.map((v, i) => (
                    <li key={`pv-${i}`}>{typeof v === 'string' ? v : JSON.stringify(v)}</li>
                  ))}
                </ul>
              </div>
            )}

            {patch.policy_result.flags && patch.policy_result.flags.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-bold">Flags:</span>
                {patch.policy_result.flags.map((f, i) => (
                  <span
                    key={`pf-${i}`}
                    className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300 text-[10px] font-bold"
                  >
                    {typeof f === 'string' ? f : JSON.stringify(f)}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Rationale & Integrity Note */}
        <div className="space-y-2">
          <div className="text-[#1F2A44] bg-[#F4F1E8] p-3.5 rounded-lg border border-[#CDC5B4] leading-relaxed">
            <span className="text-amber-800 font-bold block mb-1">Proposed Rationale:</span>
            {patch.rationale || 'Address identified error and align environment/settings.'}
          </div>

          {isConfigAlignment && (
            <div className="p-2.5 rounded bg-[#F4F1E8] border border-rust/40 text-[#1F2A44] text-[11px] flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rust"></span>
              <span className="italic font-serif">
                "Integrity Note: Justified by a paper-stated value, not by the target metric."
              </span>
            </div>
          )}
        </div>

        {/* Evidence Citations */}
        {patch.evidence && patch.evidence.length > 0 && (
          <div className="flex items-center gap-2 pt-1">
            <span className="text-[#4A5470] text-xs">Citing Evidence Artifacts:</span>
            <div className="flex flex-wrap gap-1.5">
              {patch.evidence.map((eid) => (
                <EvidenceChip key={eid} id={eid} onClick={onSelectEvidence} />
              ))}
            </div>
          </div>
        )}

        {/* Edit Patch Editor (if isEditing) */}
        {isEditing && (
          <div className="space-y-2 p-3.5 rounded-lg bg-amber-50/70 border border-amber-300">
            <div className="flex items-center justify-between">
              <span className="text-amber-900 font-bold uppercase tracking-wider text-[11px]">
                Edit Patch Operations (JSON)
              </span>
              <span className="text-[10px] text-amber-800 font-normal">
                Subject to strict Policy P1–P10 re-evaluation and Critic review.
              </span>
            </div>
            <textarea
              value={editsText}
              onChange={(e) => setEditsText(e.target.value)}
              rows={6}
              className="w-full bg-[#FAF7F0] border border-amber-400 rounded p-2.5 font-mono text-xs text-[#1F2A44] focus:outline-none focus:border-rust"
            />
            {editError && (
              <div className="p-2 rounded bg-red-100 border border-red-300 text-red-800 text-[11px]">
                {editError}
              </div>
            )}
          </div>
        )}

        {/* Diff preview */}
        <div className="space-y-1.5">
          <span className="text-[#4A5470] text-xs font-semibold uppercase tracking-wider block">
            Target Unified Diff:
          </span>
          <div className="p-4 bg-[#FAF7F0] border border-[#CDC5B4] rounded-lg max-h-56 overflow-y-auto leading-relaxed text-[11px]">
            {patch.diff ? (
              patch.diff.split('\n').map((line, idx) => {
                let color = 'text-[#1F2A44]';
                if (line.startsWith('+')) color = 'text-[#15803D] bg-[#DCFCE7] px-1 rounded block font-medium';
                if (line.startsWith('-')) color = 'text-[#B91C1C] bg-[#FEE2E2] px-1 rounded block font-medium';
                if (line.startsWith('@@')) color = 'text-[#8F3F20] bg-[#FEF3C7] px-1 block font-bold';
                return <div key={idx} className={color}>{line}</div>;
              })
            ) : (
              <div className="text-[#4A5470] italic">No textual diff available</div>
            )}
          </div>
        </div>

        {/* Embedded Critic Panel */}
        <CriticPanel review={criticReview} />

        {/* Extra Confirmation Checkbox */}
        {requiresExtraConfirm && !isEditing && (
          <label className="flex items-start gap-3 p-3 rounded-lg bg-amber-50 border border-amber-300 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={extraConfirmed}
              onChange={(e) => setExtraConfirmed(e.target.checked)}
              className="mt-0.5 rounded accent-rust focus:ring-rust"
            />
            <span className="text-amber-900 text-xs leading-relaxed">
              I have verified the flagged banner and explicitly confirm applying this change despite warnings.
            </span>
          </label>
        )}

        {/* Optional Comment */}
        <div className="space-y-1">
          <label className="text-[#4A5470] text-[11px] block">Operator Notes (optional):</label>
          <input
            type="text"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="e.g., Verified against Figure 2 in paper..."
            className="w-full bg-[#FAF7F0] border border-[#CDC5B4] rounded-lg px-3 py-2 text-xs text-[#1F2A44] focus:outline-none focus:border-rust"
          />
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#CDC5B4]">
          <button
            type="button"
            onClick={handleReject}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-sm bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 font-bold text-xs uppercase tracking-wider transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            <span>Reject Patch</span>
          </button>

          {isEditing ? (
            <button
              type="button"
              onClick={handleApplyEdit}
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-5 py-2.5 rounded-sm bg-amber-700 hover:bg-amber-800 text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-amber-950 shadow-md active:scale-95 transition-all disabled:opacity-40"
            >
              <Check className="w-4 h-4 stroke-[3] text-[#FAF7F0]" />
              <span>{isSubmitting ? 'Evaluating Policy...' : 'Validate & Apply Edit'}</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={handleApprove}
              disabled={!canApprove || isSubmitting}
              className="flex items-center gap-1.5 px-5 py-2.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-[#7A3317] shadow-md active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Check className="w-4 h-4 stroke-[3] text-[#FAF7F0]" />
              <span>{isSubmitting ? 'Approving...' : 'Approve & Apply'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

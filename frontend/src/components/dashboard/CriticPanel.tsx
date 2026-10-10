import React from 'react';
import { Check, X, ShieldCheck, AlertTriangle, ListChecks } from 'lucide-react';
import type { CriticReview } from '../../api/types';

interface CriticPanelProps {
  review?: CriticReview | null;
}

const CHECK_LABELS: Record<string, string> = {
  cause_is_cited_and_exists: 'Cause is cited & verified in logs/repo',
  evidence_actually_supports_cause: 'Evidence directly supports diagnosis',
  change_is_minimal: 'Change is strictly minimal & targeted',
  files_in_scope: 'Only permitted files modified (<= 5 files)',
  not_metric_chasing: 'Not tuning parameters to chase metric',
  value_has_paper_or_error_provenance: 'Values grounded in paper text or traceback',
  no_change_to_evaluation_or_data_semantics: 'Evaluation logic & data untouched',
  alternative_explanations_considered: 'Alternative diagnoses evaluated',
  reversible_and_smoke_testable: 'Patch is atomic & passes smoke test',
};

export const CriticPanel: React.FC<CriticPanelProps> = ({ review }) => {
  if (!review) {
    return (
      <div className="p-4 rounded-lg bg-[#FAF7F0] border border-[#CDC5B4] text-xs font-mono text-[#4A5470] shadow-sm">
        <span className="text-purple-800 font-bold">Independent Review: </span>
        No Critic review packet submitted yet.
      </div>
    );
  }

  const isSupported = review.verdict === 'SUPPORTED';

  return (
    <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-4 space-y-4 font-mono text-xs shadow-sm text-[#1F2A44]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-purple-700" />
          <span className="font-semibold text-[#1F2A44] uppercase tracking-wider text-[11px]">
            Critic Review Packet (Round {review.round})
          </span>
        </div>

        <span
          className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${
            isSupported
              ? 'bg-purple-100 text-purple-800 border-purple-400'
              : 'bg-red-100 text-red-800 border-red-400'
          }`}
        >
          {review.verdict}
        </span>
      </div>

      {/* 9-Point Inspection Checklist */}
      <div className="space-y-1.5">
        <span className="text-[11px] text-[#4A5470] font-semibold uppercase tracking-wider block mb-2">
          9-Point Verification Checklist:
        </span>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {Object.entries(review.checks || {}).map(([key, passed]) => (
            <div
              key={key}
              className={`flex items-start gap-2 p-2 rounded border text-[11px] leading-tight ${
                passed
                  ? 'bg-[#F4F1E8] border-[#CDC5B4] text-[#1F2A44]'
                  : 'bg-red-50 border-red-300 text-red-900'
              }`}
            >
              <span className={`p-0.5 rounded ${passed ? 'text-emerald-700' : 'text-red-700'}`}>
                {passed ? <Check className="w-3.5 h-3.5 stroke-[3]" /> : <X className="w-3.5 h-3.5 stroke-[3]" />}
              </span>
              <span>{CHECK_LABELS[key] || key}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Objections / Warnings */}
      {review.objections && review.objections.length > 0 && (
        <div className="p-3 rounded bg-red-50 border border-red-300 space-y-1 text-red-900">
          <div className="flex items-center gap-1.5 font-bold text-red-700">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>Critic Objections:</span>
          </div>
          <ul className="list-disc list-inside space-y-0.5 text-[11px]">
            {review.objections.map((obj, i) => (
              <li key={i}>{obj}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Required changes */}
      {review.required_changes && review.required_changes.length > 0 && (
        <div className="p-3 rounded bg-amber-50 border border-amber-300 space-y-1 text-amber-900">
          <div className="flex items-center gap-1.5 font-bold text-amber-800">
            <ListChecks className="w-3.5 h-3.5" />
            <span>Required Changes:</span>
          </div>
          <ul className="list-disc list-inside space-y-0.5 text-[11px]">
            {review.required_changes.map((req, i) => (
              <li key={`rc-${i}`}>{req}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Verbatim verified evidence */}
      {review.verified_evidence && review.verified_evidence.length > 0 && (
        <div className="p-3 rounded bg-[#F4F1E8] border border-[#CDC5B4] space-y-1 text-[11px]">
          <span className="text-[#4A5470] font-semibold block">Verified Evidence Quotes:</span>
          {review.verified_evidence.map((ve, idx) => (
            <div key={idx} className="text-[#1F2A44] italic">
              <span className="text-rust font-mono not-italic font-bold">{ve.id}: </span>
              "{ve.what_i_found}"
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

import React, { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, ShieldAlert } from 'lucide-react';
import type { ProjectStateSummary } from '../../api/types';

interface PreflightNoticesProps {
  preflight?: ProjectStateSummary['preflight'];
  unresolvedIssues?: string[];
}

export const PreflightNotices: React.FC<PreflightNoticesProps> = ({
  preflight,
  unresolvedIssues,
}) => {
  const [open, setOpen] = useState(true);

  const blockers = preflight?.blockers ?? [];
  const warnings = preflight?.warnings ?? [];
  const issues = unresolvedIssues ?? [];
  const total = blockers.length + warnings.length + issues.length;

  if (total === 0) return null;

  const hasBlockers = blockers.length > 0;

  return (
    <div
      className={`rounded-xl border shadow-sm font-mono text-xs ${
        hasBlockers ? 'bg-red-50 border-red-300' : 'bg-[#FEF3C7] border-amber-500/70'
      }`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 p-3 text-left"
      >
        <span className="flex items-center gap-2 font-bold uppercase tracking-wider">
          {hasBlockers ? (
            <ShieldAlert className="w-4 h-4 text-red-700" />
          ) : (
            <AlertTriangle className="w-4 h-4 text-amber-700" />
          )}
          <span className={hasBlockers ? 'text-red-900' : 'text-amber-900'}>
            {hasBlockers
              ? `${blockers.length} blocker${blockers.length === 1 ? '' : 's'}`
              : 'Preflight notices'}
            {' · '}
            {total} item{total === 1 ? '' : 's'}
          </span>
        </span>
        {open ? (
          <ChevronDown className="w-4 h-4 text-[#4A5470]" />
        ) : (
          <ChevronRight className="w-4 h-4 text-[#4A5470]" />
        )}
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3">
          {hasBlockers && (
            <Group label="Blockers" items={blockers} tone="text-red-900" />
          )}
          {warnings.length > 0 && (
            <Group label="Warnings" items={warnings} tone="text-amber-900" />
          )}
          {issues.length > 0 && (
            <Group label="Unresolved issues" items={issues} tone="text-amber-900" />
          )}
          {preflight?.triage_verdict && (
            <div className="text-[11px] text-[#4A5470] pt-2 border-t border-[#CDC5B4]/60">
              Triage: <span className="font-bold">{preflight.triage_verdict}</span>
              {preflight.triage_reason ? ` — ${preflight.triage_reason}` : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const Group: React.FC<{ label: string; items: string[]; tone: string }> = ({
  label,
  items,
  tone,
}) => (
  <div className="space-y-1">
    <div className="text-[10px] uppercase tracking-wider text-[#4A5470] font-bold">{label}</div>
    <ul className={`space-y-1 list-disc list-inside leading-relaxed ${tone}`}>
      {items.map((text, idx) => (
        <li key={`${label}-${idx}`}>{text}</li>
      ))}
    </ul>
  </div>
);

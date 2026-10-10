import React, { useEffect, useState } from 'react';
import { FileSearch, AlertTriangle } from 'lucide-react';
import { fetchEvidenceLedger } from '../../api/client';
import type { EvidenceItem } from '../../api/types';

interface EvidenceLedgerProps {
  projectId: string;
  onSelectEvidence?: (id: string) => void;
  /** Render inside an existing card rather than drawing its own. */
  bare?: boolean;
}

export const EvidenceLedger: React.FC<EvidenceLedgerProps> = ({
  projectId,
  onSelectEvidence,
  bare = false,
}) => {
  const [items, setItems] = useState<EvidenceItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    fetchEvidenceLedger(projectId)
      .then((data) => { if (!cancelled) setItems(data); })
      .catch((err) => { if (!cancelled) setError(err?.message || 'Failed to load evidence'); });
    return () => { cancelled = true; };
  }, [projectId]);

  const missing = (items ?? []).filter((i) => i.available === false);

  const body = (
    <>
      {error && <p className="text-red-700 font-bold">{error}</p>}

      {items !== null && items.length === 0 && (
        <p className="text-[#4A5470] leading-relaxed">
          No evidence was recorded for this run. A reproduction that needed no diagnosis can
          legitimately cite little, but an empty ledger means nothing here is independently
          traceable.
        </p>
      )}

      {missing.length > 0 && (
        <div className="p-2.5 rounded bg-amber-50 border border-amber-300 text-amber-900 text-[11px] flex items-start gap-2">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>
            {missing.length} entr{missing.length === 1 ? 'y was' : 'ies were'} recorded by the
            agent but can no longer be served — the artifact or its ledger entry is gone.
          </span>
        </div>
      )}

      {items !== null && items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                <th className="py-2 px-2">ID</th>
                <th className="py-2 px-2">Type</th>
                <th className="py-2 px-2">Captured by</th>
                <th className="py-2 px-2">Excerpt</th>
                <th className="py-2 px-2">SHA-256</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#CDC5B4]/50">
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={item.available === false ? 'opacity-60' : 'hover:bg-[#F4F1E8] cursor-pointer'}
                  onClick={() => item.available !== false && onSelectEvidence?.(item.id)}
                >
                  <td className="py-2 px-2 font-bold text-rust">{item.id}</td>
                  <td className="py-2 px-2">
                    {item.available === false ? (
                      <span className="text-amber-800 font-semibold">unavailable</span>
                    ) : (
                      <span className="px-1.5 py-0.5 rounded bg-[#E5DFD3] border border-[#CDC5B4] text-[10px] font-bold">
                        {item.type}
                      </span>
                    )}
                  </td>
                  <td className="py-2 px-2 text-[#4A5470]">{item.created_by_tool ?? '—'}</td>
                  <td className="py-2 px-2 text-[#1F2A44] max-w-[22rem] truncate">
                    {item.excerpt ? item.excerpt.replace(/\s+/g, ' ').slice(0, 120) : '—'}
                  </td>
                  <td className="py-2 px-2 font-mono text-[10px] text-[#4A5470]">
                    {item.sha256 ? item.sha256.slice(0, 10) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  if (bare) return <div className="space-y-3 font-mono text-xs text-[#1F2A44]">{body}</div>;

  return (
    <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl overflow-hidden shadow-sm font-mono text-xs text-[#1F2A44]">
      <div className="px-4 py-2.5 bg-[#F4F1E8] border-b border-[#CDC5B4] font-semibold uppercase tracking-wider text-[11px] flex items-center justify-between">
        <span className="flex items-center gap-2">
          <FileSearch className="w-3.5 h-3.5 text-rust" />
          Evidence Ledger
        </span>
        <span className="text-[#4A5470] font-normal">
          {items === null ? 'loading…' : `${items.length} entr${items.length === 1 ? 'y' : 'ies'}`}
        </span>
      </div>
      <div className="p-4 space-y-3">{body}</div>
    </div>
  );
};

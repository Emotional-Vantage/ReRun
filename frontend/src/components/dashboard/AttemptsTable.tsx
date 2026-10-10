import React from 'react';
import type { Attempt, Claim } from '../../api/types';
import { CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

interface AttemptsTableProps {
  attempts: Attempt[];
  /** The project's claims, used to find which metric key this run was judged on. */
  claims?: Claim[];
}

const observedMetric = (att: Attempt, claims: Claim[]): number | null => {
  const metrics = att.metrics ?? {};
  for (const claim of claims) {
    for (const key of [claim.result_key, claim.metric, claim.id]) {
      if (key && metrics[key] !== undefined && metrics[key] !== null) {
        const value = Number(metrics[key]);
        if (!Number.isNaN(value)) return value;
      }
    }
  }
  const comparison = att.comparison?.[0];
  if (comparison && comparison.observed !== null && comparison.observed !== undefined) {
    return Number(comparison.observed);
  }
  return null;
};

export const AttemptsTable: React.FC<AttemptsTableProps> = ({ attempts, claims = [] }) => {
  if (!attempts || attempts.length === 0) {
    return (
      <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 text-center text-[#4A5470] font-mono text-xs shadow-sm">
        No runs yet. Container executions will be tracked here.
      </div>
    );
  }

  return (
    <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl overflow-hidden shadow-sm font-mono text-xs text-[#1F2A44]">
      <div className="px-4 py-2.5 bg-[#F4F1E8] border-b border-[#CDC5B4] font-semibold text-[#1F2A44] uppercase tracking-wider text-[11px] flex items-center justify-between">
        <span>Runs and what each one measured</span>
        <span className="text-[#4A5470] font-normal">{attempts.length} run{attempts.length > 1 ? 's' : ''} recorded</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] bg-[#FAF7F0]">
              <th className="py-2.5 px-4">Run</th>
              <th className="py-2.5 px-4">Finished cleanly?</th>
              <th className="py-2.5 px-4">What went wrong</th>
              <th className="py-2.5 px-4">Took</th>
              <th className="py-2.5 px-4">Changes used</th>
              <th className="py-2.5 px-4">We measured</th>
              <th className="py-2.5 px-4">Result</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#CDC5B4]/50">
            {attempts.map((att) => {
              const comp = att.comparison?.[0];
              const isCrash = att.exit_code !== 0;
              const withinTol = comp?.within_tolerance;
              const metricVal = observedMetric(att, claims);
              const patchIds = att.patches_applied ?? att.used_patches ?? [];

              return (
                <tr key={att.n} className="hover:bg-[#F4F1E8]/80 transition-colors">
                  <td className="py-2.5 px-4 font-bold text-[#1F2A44]">#{att.n}</td>
                  <td className="py-2.5 px-4">
                    <span
                      title={`exit code ${att.exit_code}`}
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        isCrash ? 'bg-red-100 text-red-700 border border-red-300' : 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                      }`}
                    >
                      {/* The column asks a yes/no question, so answer it. The raw code is
                          kept in the title for anyone who wants it. */}
                      {att.exit_code === 0 ? 'yes' : 'no'}
                    </span>
                  </td>
                  <td className="py-2.5 px-4">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {att.timed_out && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-400 text-[10px] font-bold">
                          TIMEOUT
                        </span>
                      )}
                      {att.oom && (
                        <span className="px-1.5 py-0.5 rounded bg-red-100 text-red-800 border border-red-300 text-[10px] font-bold">
                          OOM
                        </span>
                      )}
                      {att.error_class ? (
                        <span className="text-amber-800 font-semibold">{att.error_class}</span>
                      ) : att.timed_out || att.oom ? null : isCrash ? (
                        <span className="text-red-700 font-medium">It stopped with an error</span>
                      ) : (
                        <span className="text-[#4A5470]">Nothing — it ran fine</span>
                      )}
                    </div>
                  </td>
                  <td className="py-2.5 px-4 text-[#4A5470]">
                    {att.duration_s !== undefined && att.duration_s !== null
                      ? `${Number(att.duration_s).toFixed(1)}s`
                      : <span className="text-[#CDC5B4]">—</span>}
                  </td>
                  <td className="py-2.5 px-4">
                    {patchIds.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {patchIds.map((pid) => (
                          <span
                            key={pid}
                            className="px-1.5 py-0.5 rounded bg-[#E5DFD3] border border-[#CDC5B4] text-[10px] font-bold"
                          >
                            {pid}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-[#CDC5B4]">none</span>
                    )}
                  </td>
                  <td className="py-2.5 px-4 text-[#1F2A44]">
                    {metricVal !== undefined && metricVal !== null ? (
                      <span className="text-rust font-bold">{Number(metricVal).toFixed(4)}</span>
                    ) : (
                      <span className="text-[#CDC5B4]">—</span>
                    )}
                  </td>
                  <td className="py-2.5 px-4">
                    {withinTol === true ? (
                      <span className="inline-flex items-center gap-1.5 text-emerald-700 font-bold">
                        <CheckCircle2 className="w-4 h-4" /> Matched
                      </span>
                    ) : withinTol === false ? (
                      <span className="inline-flex items-center gap-1.5 text-red-700 font-bold">
                        <XCircle className="w-4 h-4" /> Did not match
                      </span>
                    ) : isCrash ? (
                      <span className="inline-flex items-center gap-1.5 text-[#4A5470]">
                        <AlertCircle className="w-4 h-4" /> No number
                      </span>
                    ) : (
                      <span className="text-[#CDC5B4]">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

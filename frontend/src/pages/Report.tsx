import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Download,
  ArrowLeft,
  AlertTriangle,
  Copy,
  Check,
  Package,
  FileText,
  Trash2,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ReferenceLine,
} from 'recharts';
import { NavbarApp } from '../components/layout/NavbarApp';
import { Footer } from '../components/layout/Footer';
import { Stamp } from '../components/ui/Stamp';
import { EvidenceChip } from '../components/ui/EvidenceChip';
import { EvidenceDrawer } from '../components/ui/EvidenceDrawer';
import { EvidenceLedger } from '../components/dashboard/EvidenceLedger';
import { fetchReport, fetchReportMarkdown } from '../api/client';
import type { ReportData } from '../api/types';

export const Report: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [copiedMd, setCopiedMd] = useState(false);
  const [copyError, setCopyError] = useState(false);

  useEffect(() => {
    if (!id) return;
    fetchReport(id)
      .then(setReport)
      .catch((err) => console.error('Failed to load report', err))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col items-center justify-center font-mono">
        <div className="w-10 h-10 border-4 border-rust border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-xs text-[#4A5470] uppercase tracking-wider font-semibold">
          Loading certified reproduction report...
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col items-center justify-center font-mono p-6">
        <p className="text-sm text-fail mb-4 font-bold">
          Report not available yet for this project.
        </p>
        <Link to={`/p/${id}`} className="text-xs text-rust hover:underline">
          ← Return to Console
        </Link>
      </div>
    );
  }

  // Build Recharts data comparing unpatched (Run 1) vs final patched run vs paper claim
  const attempts = report.attempts || [];
  const claim = report.claims?.[0];

  // Everything below comes from the backend's verified comparison. Nothing is invented.
  //
  // A `?? 0.956` fallback here meant a run that crashed and produced no metrics displayed
  // the benchmark's expected answer as its "observed mean", with an absolute gap of 0.0000
  // and a hardcoded "WITHIN TOLERANCE" status: the page asserted a successful reproduction
  // of a run that never executed.
  const comparisonPoints = report.runs_summary?.comparison_chart ?? [];
  const metricKey = claim?.metric ?? claim?.result_key ?? 'metric';
  const reportedTarget = claim?.reported ?? null;
  const toleranceValue = claim?.tolerance?.value ?? null;
  const toleranceLabel =
    toleranceValue === null
      ? 'unspecified'
      : claim?.tolerance?.type === 'rel'
      ? `± ${(toleranceValue * 100).toFixed(2)}%`
      : `± ${toleranceValue.toFixed(4)}`;

  const finalPoint = comparisonPoints.length
    ? comparisonPoints[comparisonPoints.length - 1]
    : null;
  const observedFinal = finalPoint?.observed ?? null;
  const absGap =
    observedFinal !== null && reportedTarget !== null
      ? Math.abs(observedFinal - reportedTarget)
      : null;

  const fmt = (v: number | null, digits = 4) => (v === null ? '—' : v.toFixed(digits));

  // Crashed attempts are omitted from the chart rather than plotted as a fabricated value.
  const chartData = comparisonPoints
    .filter((p) => p.observed !== null)
    .map((p) => ({
      name: `Run ${p.run_n}`,
      accuracy: Number(Number(p.observed).toFixed(4)),
      target: reportedTarget ?? undefined,
    }));

  const crashedRuns = comparisonPoints.filter((p) => p.observed === null);

  // Everything below is read straight off the report. Where the backend has nothing, the
  // section does not render — no section invents its own content.
  const claims = report.claims ?? [];
  const limitations = report.limitations ?? [];
  const notChecked = report.not_checked ?? [];
  const removedStatements = report.statements_removed ?? [];
  const verification = report.verification_summary ?? null;
  const unselectedClaims = report.unselected_claims ?? [];
  const appliedPatchCount =
    report.patches_summary?.length ??
    (report.patches ?? []).filter((p) => p.status === 'applied').length;
  const narrativeGroups: Array<['findings' | 'causes' | 'fixes', string]> = [
    ['findings', 'What was found'],
    ['causes', 'Why it happened'],
    ['fixes', 'What was changed'],
  ];
  // `statements.limitations` / `.not_checked` duplicate the deterministic lists rendered in
  // Section 4, so only the narrative sections are shown here.
  const narrative = narrativeGroups
    .map(([key, label]) => ({ key, label, items: report.statements?.[key] ?? [] }))
    .filter((group) => group.items.length > 0);

  /** The latest comparison the backend computed for a given claim. */
  const comparisonForClaim = (claimId: string) => {
    for (let i = attempts.length - 1; i >= 0; i -= 1) {
      const match = attempts[i].comparison?.find((c) => c.claim_id === claimId);
      if (match) return match;
    }
    return null;
  };

  const statusCell = (within: boolean | null) =>
    within === true
      ? { text: 'WITHIN TOLERANCE', cls: 'text-emerald-700' }
      : within === false
      ? { text: 'OUTSIDE TOLERANCE', cls: 'text-red-700' }
      : { text: 'NOT MEASURED', cls: 'text-amber-800' };

  // The server renders the full report as Markdown. Assembling a four-line summary locally
  // and calling it the report quietly dropped every finding.
  const handleCopyMarkdown = async () => {
    if (!id) return;
    try {
      const md = await fetchReportMarkdown(id);
      await navigator.clipboard.writeText(md);
      setCopiedMd(true);
      setTimeout(() => setCopiedMd(false), 2000);
    } catch (err) {
      console.error('Failed to copy report markdown', err);
      setCopyError(true);
      setTimeout(() => setCopyError(false), 3000);
    }
  };

  return (
    <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col font-mono select-text">
      <NavbarApp
        projectId={id}
        benchmarkId={report.benchmark_id}
        phase="DONE"
        status={report.status}
        isReportReady={true}
      />

      <main className="flex-1 max-w-5xl w-full mx-auto p-4 sm:p-8 space-y-10">
        {/* Simulated Run Banner (R7) */}
        {report.simulated && (
          <div className="bg-amber-900/10 border-2 border-amber-600/60 rounded-xl p-4 flex items-center gap-3 text-amber-900 font-mono text-xs">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold uppercase tracking-wider">
                Simulated Execution Banner:
              </span>{' '}
              This reproduction was executed in simulation mode (synthetic execution harness /
              fake sandbox).
            </div>
          </div>
        )}

        {/* Top Header Card */}
        <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-2xl p-6 sm:p-8 shadow-md flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-3">
            <Link
              to={`/p/${id}`}
              className="inline-flex items-center gap-1.5 text-xs font-mono text-rust hover:underline font-bold"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Live Console</span>
            </Link>

            <h1 className="font-serif text-2xl sm:text-3xl font-normal uppercase tracking-wide text-[#1F2A44]">
              Reproduction Report: {report.benchmark_id || 'Custom Paper'}
            </h1>
            <p className="text-xs text-[#4A5470] font-mono">
              Verification completed across {attempts.length} run{attempts.length > 1 ? 's' : ''}{' '}
              with {report.after_n_fixes} approved patch{report.after_n_fixes > 1 ? 'es' : ''}.
            </p>

            {/* Target Repository & Paper Metadata (R7) */}
            <div className="pt-2 text-[11px] text-[#4A5470] space-y-0.5 border-t border-[#CDC5B4]/60">
              <div>
                <span className="font-bold text-[#1F2A44]">Repo:</span>{' '}
                <span className="font-mono">
                  {report.repo_url || report.benchmark_id || 'Synthetic Benchmark'}
                </span>
                {report.repo_commit && (
                  <span className="ml-2 px-1.5 py-0.5 bg-[#EDE7DB] rounded text-[10px] text-[#1F2A44]">
                    SHA: {report.repo_commit.slice(0, 8)}
                  </span>
                )}
              </div>
              {report.paper_path && (
                <div>
                  <span className="font-bold text-[#1F2A44]">Paper:</span>{' '}
                  <span className="font-mono">{report.paper_path}</span>
                </div>
              )}
            </div>
          </div>

          {/* Physical Verification Stamp */}
          <div className="shrink-0">
            <Stamp status={report.status} afterNPatches={report.after_n_fixes} />
          </div>
        </div>

        {/* Action Toolbar */}
        <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-4 text-xs font-mono">
          <span className="text-[#4A5470]">Document certified by deterministic tools</span>
          <div className="flex items-center gap-3">
            <a
              href={`/api/projects/${id}/kit`}
              download={`rerun_kit_${id}.zip`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] transition-colors uppercase tracking-wider text-[11px] font-semibold"
            >
              <Package className="w-3.5 h-3.5 text-rust" />
              <span>Reproduction Kit (.zip)</span>
            </a>
            <button
              onClick={handleCopyMarkdown}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] transition-colors uppercase tracking-wider text-[11px] font-semibold"
            >
              {copiedMd ? (
                <Check className="w-3.5 h-3.5 text-ok" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
              <span>{copyError ? 'Copy failed' : copiedMd ? 'Copied' : 'Copy Markdown'}</span>
            </button>
            <a
              href={`/api/projects/${id}/report.md`}
              download={`rerun_report_${id}.md`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] transition-colors uppercase tracking-wider text-[11px] font-semibold"
            >
              <FileText className="w-3.5 h-3.5 text-rust" />
              <span>Report (.md)</span>
            </a>
            <button
              onClick={() => window.print()}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-[#7A3317] shadow-sm active:scale-95 transition-all"
            >
              <Download className="w-3.5 h-3.5 text-[#FAF7F0]" />
              <span>Export PDF</span>
            </button>
          </div>
        </div>

        {/* SECTION 0: STATEMENT VERIFICATION LEDGER
            The report reviewer checks every statement the writer produced and strikes the
            ones it cannot support. That accounting was computed but never shown, so a
            reader could not tell a fully-supported report from a heavily-redacted one. */}
        {verification && (
          <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-5 shadow-sm font-mono text-xs text-[#1F2A44]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
                  0. Statement Verification
                </span>
                <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
                  What This Report Is Allowed To Say
                </h2>
              </div>
              <div className="flex items-center gap-4 text-[11px]">
                <div className="text-center">
                  <div className="text-lg font-bold text-[#1F2A44]">{verification.total}</div>
                  <div className="uppercase tracking-wider text-[#4A5470]">Evaluated</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-emerald-700">{verification.verified}</div>
                  <div className="uppercase tracking-wider text-[#4A5470]">Verified</div>
                </div>
                <div className="text-center">
                  <div
                    className={`text-lg font-bold ${
                      verification.removed > 0 ? 'text-red-700' : 'text-[#CDC5B4]'
                    }`}
                  >
                    {verification.removed}
                  </div>
                  <div className="uppercase tracking-wider text-[#4A5470]">Removed</div>
                </div>
              </div>
            </div>

            {narrative.map((group) => (
              <div key={group.key} className="space-y-2">
                <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                  {group.label}
                </div>
                {group.items.map((st) => (
                  <div
                    key={st.id}
                    className="p-3 rounded border border-[#CDC5B4] bg-[#F4F1E8] space-y-2"
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-1.5 py-0.5 rounded bg-[#E5DFD3] border border-[#CDC5B4] text-[10px] font-bold">
                        {st.id}
                      </span>
                      {st.kind && (
                        <span className="text-[10px] uppercase tracking-wider text-[#4A5470]">
                          {st.kind}
                        </span>
                      )}
                      {st.confidence && (
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${
                            st.confidence === 'confirmed'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : 'bg-amber-100 text-amber-900 border border-amber-300'
                          }`}
                        >
                          {st.confidence}
                        </span>
                      )}
                    </div>
                    <p className="leading-relaxed text-[#1F2A44]">{st.text}</p>
                    {st.evidence && st.evidence.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-[#CDC5B4]/50">
                        <span className="text-[10px] text-[#4A5470]">Evidence:</span>
                        {st.evidence.map((eid) => (
                          <EvidenceChip key={eid} id={eid} onClick={setSelectedEvidenceId} />
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}

            {removedStatements.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-red-800 font-bold">
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>Struck from this report ({removedStatements.length})</span>
                </div>
                {removedStatements.map((rm) => (
                  <div
                    key={rm.statement_id}
                    className="p-3 rounded border border-red-300 bg-red-50 space-y-1.5"
                  >
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded bg-red-100 border border-red-300 text-[10px] font-bold text-red-900">
                        {rm.statement_id}
                      </span>
                      <span className="text-[10px] uppercase tracking-wider text-red-800">
                        {rm.section}
                      </span>
                    </div>
                    <p className="leading-relaxed text-red-900 line-through decoration-red-400">
                      {rm.text}
                    </p>
                    {rm.violations && rm.violations.length > 0 && (
                      <ul className="list-disc list-inside text-[11px] text-red-800">
                        {rm.violations.map((v, i) => (
                          <li key={`${rm.statement_id}-v-${i}`}>{v}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {/* SECTION 1: VERIFIED METRIC COMPARISON (RECHARTS BAR CHART) */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-6 shadow-sm font-mono text-xs text-[#1F2A44]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
                1. Computational Metric Verification
              </span>
              <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
                Unpatched vs. Patched Headline Metric
              </h2>
              <p className="text-[#4A5470] font-sans text-xs">
                Both unpatched and final runs are explicitly displayed against the paper's target
                tolerance band.
              </p>
            </div>
            <div className="shrink-0 flex items-center gap-2.5 px-3.5 py-2 rounded-lg bg-[#FAF7F0] border border-[#CDC5B4] shadow-sm text-xs font-mono">
              <span className="text-[#4A5470]">Target Metric:</span>
              <span className="font-bold text-rust text-sm">{fmt(reportedTarget)}</span>
              {claim?.tolerance && (
                <span className="text-[#4A5470] text-[11px] font-semibold">
                  (±{typeof claim.tolerance === 'object' ? claim.tolerance.value : claim.tolerance})
                </span>
              )}
            </div>
          </div>

          {/* Recharts Bar Chart */}
          <div className="h-72 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 32, right: 35, left: 0, bottom: 8 }}>
                <XAxis dataKey="name" stroke="#78716C" fontSize={11} />
                <YAxis domain={[0, 1.15]} stroke="#78716C" fontSize={11} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#FAF7F0',
                    borderColor: '#CDC5B4',
                    borderRadius: '6px',
                    color: '#1F2A44',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  }}
                />
                <Legend />
                <ReferenceLine
                  y={reportedTarget ?? undefined}
                  stroke="#B8572F"
                  strokeDasharray="6 4"
                  strokeWidth={1.5}
                  label={(props: any) => {
                    const { viewBox } = props;
                    if (!viewBox) return null;
                    const x = viewBox.x + viewBox.width / 2;
                    const y = viewBox.y - 14;
                    return (
                      <g>
                        <rect
                          x={x - 100}
                          y={y - 12}
                          width={200}
                          height={24}
                          rx={5}
                          fill="#FAF7F0"
                          stroke="#B8572F"
                          strokeWidth={1.5}
                        />
                        <text
                          x={x}
                          y={y + 4}
                          textAnchor="middle"
                          fill="#8F3F20"
                          fontSize={11}
                          fontFamily="JetBrains Mono, monospace"
                          fontWeight="bold"
                        >
                          Paper Target: {fmt(reportedTarget)}
                        </text>
                      </g>
                    );
                  }}
                />
                <Bar
                  dataKey="accuracy"
                  fill="#B8572F"
                  name="Observed Accuracy"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={90}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Gap Comparison Table */}
          <div className="overflow-x-auto pt-4 border-t border-[#CDC5B4]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                  <th className="py-2 px-3">Metric Key</th>
                  <th className="py-2 px-3">Paper Reported</th>
                  <th className="py-2 px-3">Tolerance</th>
                  <th className="py-2 px-3">Observed Mean</th>
                  <th className="py-2 px-3">Abs Gap</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#CDC5B4]/50">
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-[#1F2A44]">{metricKey}</td>
                  <td className="py-2.5 px-3 text-amber-800 font-bold">{fmt(reportedTarget)}</td>
                  <td className="py-2.5 px-3 text-[#4A5470]">{toleranceLabel}</td>
                  <td className="py-2.5 px-3 text-rust font-bold">
                    {observedFinal === null ? 'not measured' : fmt(observedFinal)}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[#1F2A44]">{fmt(absGap)}</td>
                  <td
                    className={`py-2.5 px-3 font-bold ${
                      statusCell(finalPoint?.within_tolerance ?? null).cls
                    }`}
                  >
                    {statusCell(finalPoint?.within_tolerance ?? null).text}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Every selected claim, not only the first. The chart above tracks the headline
              metric; a paper with several claims had the rest silently dropped. */}
          {claims.length > 1 && (
            <div className="overflow-x-auto pt-4 border-t border-[#CDC5B4] space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                All verified claims ({claims.length})
              </div>
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                    <th className="py-2 px-3">Claim</th>
                    <th className="py-2 px-3">Metric</th>
                    <th className="py-2 px-3">Reported</th>
                    <th className="py-2 px-3">Observed</th>
                    <th className="py-2 px-3">Gap</th>
                    <th className="py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map((c) => {
                    const cmp = comparisonForClaim(c.id);
                    const cell = statusCell(cmp ? cmp.within_tolerance : null);
                    return (
                      <tr key={c.id} className="border-b border-[#CDC5B4]/50">
                        <td className="py-2 px-3 font-bold">{c.id}</td>
                        <td className="py-2 px-3 font-mono">{c.metric || c.result_key || '—'}</td>
                        <td className="py-2 px-3">{fmt(c.reported ?? null)}</td>
                        <td className="py-2 px-3">{fmt(cmp?.observed ?? null)}</td>
                        <td className="py-2 px-3">{fmt(cmp?.abs_gap ?? null)}</td>
                        <td className={`py-2 px-3 font-bold ${cell.cls}`}>{cell.text}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Claims the operator chose not to verify. Omitting them made the report look
              like it covered the whole paper. */}
          {unselectedClaims.length > 0 && (
            <div className="pt-4 border-t border-[#CDC5B4] space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                Not verified in this run ({unselectedClaims.length})
              </div>
              <ul className="space-y-1 text-[#4A5470] list-disc list-inside leading-relaxed">
                {unselectedClaims.map((c) => (
                  <li key={c.id}>
                    <span className="font-bold text-[#1F2A44]">{c.id}</span>{' '}
                    {c.statement || c.metric}
                    {c.reported !== undefined && c.reported !== null && (
                      <span className="font-mono"> — reported {c.reported}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Per-attempt detail, including attempts that produced no metric at all. */}
          {comparisonPoints.length > 0 && (
            <div className="overflow-x-auto pt-4 border-t border-[#CDC5B4]">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                    <th className="py-2 px-3">Attempt</th>
                    <th className="py-2 px-3">Exit Code</th>
                    <th className="py-2 px-3">Observed</th>
                    <th className="py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#CDC5B4]/50">
                  {comparisonPoints.map((pt) => {
                    const st = statusCell(pt.within_tolerance);
                    return (
                      <tr key={pt.run_n}>
                        <td className="py-2.5 px-3 font-semibold text-[#1F2A44]">Run {pt.run_n}</td>
                        <td
                          className={`py-2.5 px-3 font-mono font-bold ${
                            pt.exit_code === 0 ? 'text-emerald-700' : 'text-red-700'
                          }`}
                        >
                          {pt.exit_code === null ? 'killed' : pt.exit_code}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[#1F2A44]">
                          {pt.observed === null ? 'no metric produced' : fmt(pt.observed)}
                        </td>
                        <td className={`py-2.5 px-3 font-bold ${st.cls}`}>{st.text}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {crashedRuns.length > 0 && (
                <p className="pt-3 text-[11px] text-amber-800 font-mono">
                  {crashedRuns.length} attempt{crashedRuns.length === 1 ? '' : 's'} produced no
                  metric and {crashedRuns.length === 1 ? 'is' : 'are'} omitted from the chart above
                  rather than plotted as a value.
                </p>
              )}
            </div>
          )}
        </section>

        {/* SECTION 2: RUNS AND PATCHES TABLE */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-6 shadow-sm font-mono text-xs text-[#1F2A44]">
          <div className="space-y-1.5">
            <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
              2. Provenance & Applied Patches
            </span>
            <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
              Applied Fixes with Critic Review
            </h2>
            {/* patches_summary is the backend's applied subset; the list below is every
                proposal. Stating both stops an applied count being read off a list that
                also contains rejected and dropped patches. */}
            {report.patches && report.patches.length > 0 && (
              <p className="text-[#4A5470] font-sans text-xs">
                {appliedPatchCount} of {report.patches.length} proposed patch
                {report.patches.length === 1 ? '' : 'es'} applied.
              </p>
            )}
          </div>

          {report.patches && report.patches.length > 0 ? (
            <div className="space-y-4">
              {report.patches.map((p, idx) => (
                <div
                  key={p.id || idx}
                  className="p-4 rounded-lg bg-[#F4F1E8] border border-[#CDC5B4] space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-rust">{p.id || `P-${idx + 1}`}</span>
                      <span className="px-2 py-0.5 rounded bg-[#FAF7F0] text-[#1F2A44] border border-[#CDC5B4] text-[10px] uppercase tracking-wider font-bold">
                        {p.risk_class}
                      </span>
                    </div>
                    {/* Reflect the patch's real status. This was hardcoded "Applied & Verified",
                        so a dropped, rejected or reverted patch was presented as applied. */}
                    <span
                      className={`font-bold uppercase tracking-wider ${
                        p.status === 'applied'
                          ? 'text-emerald-700'
                          : p.status === 'rejected' ||
                            p.status === 'reverted' ||
                            p.status === 'dropped'
                          ? 'text-red-700'
                          : 'text-amber-800'
                      }`}
                    >
                      {p.status === 'applied' ? 'Applied & Verified' : p.status ?? 'unknown'}
                    </span>
                  </div>

                  <p className="text-[#1F2A44] font-sans text-xs">{p.rationale}</p>

                  {p.evidence && p.evidence.length > 0 && (
                    <div className="flex items-center gap-2 pt-2 border-t border-[#CDC5B4]/50">
                      <span className="text-[#4A5470] text-[11px]">Cited Evidence:</span>
                      {p.evidence.map((eid) => (
                        <EvidenceChip
                          key={eid}
                          id={eid}
                          onClick={(eId) => setSelectedEvidenceId(eId)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : report.status === 'REPRODUCED' ? (
            <p className="text-[#4A5470]">
              Zero patches were required; code reproduced out of the box.
            </p>
          ) : (
            <p className="text-[#4A5470]">
              No patch was applied. The verdict is{' '}
              <span className="font-bold text-rust">{report.status}</span>
              {report.reason ? `: ${report.reason}` : ''}. An empty patch list does not mean the
              reproduction succeeded.
            </p>
          )}
        </section>

        {/* SECTION 3: CONFIG AUDIT TABLE */}
        {report.config_diff && report.config_diff.length > 0 && (
          <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-4 shadow-sm font-mono text-xs text-[#1F2A44]">
            <div className="space-y-1.5">
              <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
                3. Parameter Audit
              </span>
              <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
                Configuration Audit vs. Paper Text
              </h2>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                    <th className="py-2 px-3">Parameter Key</th>
                    <th className="py-2 px-3">Effective Config</th>
                    <th className="py-2 px-3">Paper Value</th>
                    <th className="py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#CDC5B4]/50">
                  {report.config_diff.map((cd, idx) => (
                    <tr key={idx}>
                      <td className="py-2.5 px-3 font-semibold text-[#1F2A44]">{cd.key}</td>
                      <td className="py-2.5 px-3 text-red-700 font-bold">
                        {String(cd.effective_value)}
                      </td>
                      <td className="py-2.5 px-3 text-emerald-700 font-bold">
                        {String(cd.paper_value)}
                      </td>
                      <td className="py-2.5 px-3 text-[#4A5470]">{cd.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* SECTION 3b: EVIDENCE LEDGER — the chain of custody behind every statement above. */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-4 shadow-sm font-mono text-xs text-[#1F2A44]">
          <div className="space-y-1.5">
            <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
              3. Chain Of Custody
            </span>
            <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
              Evidence Ledger
            </h2>
          </div>
          <EvidenceLedger projectId={id || ''} onSelectEvidence={setSelectedEvidenceId} bare />
        </section>

        {/* SECTION 4: LIMITS AND WHAT WAS NOT CHECKED
            These are the backend's per-project lists. They used to be three hardcoded
            bullets that never changed, which presented boilerplate as this run's findings. */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-5 shadow-sm text-xs font-mono text-[#1F2A44]">
          <div className="flex items-center gap-2 text-rust font-bold uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4" />
            <span>Honesty & Limitations: What Was Not Checked</span>
          </div>

          {limitations.length > 0 && (
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                Limitations of this reproduction
              </div>
              <ul className="space-y-2 text-[#4A5470] leading-relaxed list-disc list-inside">
                {limitations.map((text, idx) => (
                  <li key={`lim-${idx}`}>{text}</li>
                ))}
              </ul>
            </div>
          )}

          {notChecked.length > 0 && (
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                Not checked
              </div>
              <ul className="space-y-2 text-[#4A5470] leading-relaxed list-disc list-inside">
                {notChecked.map((text, idx) => (
                  <li key={`nc-${idx}`}>{text}</li>
                ))}
              </ul>
            </div>
          )}

          {limitations.length === 0 && notChecked.length === 0 && (
            <p className="text-[#4A5470] leading-relaxed">
              This report records no limitations. That is unusual — treat it as a gap in the report
              rather than as a guarantee.
            </p>
          )}
        </section>
      </main>

      {/* Persistent Kraft Footer */}
      <Footer />

      {/* Evidence Drawer */}
      <EvidenceDrawer
        projectId={id || ''}
        evidenceId={selectedEvidenceId}
        onClose={() => setSelectedEvidenceId(null)}
      />
    </div>
  );
};

export default Report;

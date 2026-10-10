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

/**
 * One plain-English sentence per verdict.
 *
 * The verdict used to be shown only as the raw enum plus a stamp, which told a reader who
 * already knew the vocabulary what had happened and told everyone else nothing. The wording
 * below never softens a negative result: a run that did not reproduce says so.
 */
const VERDICT_SENTENCE: Record<ReportData['status'], string> = {
  REPRODUCED: "We ran this paper's code and got the result the paper reports.",
  PARTIALLY_REPRODUCED:
    "We ran this paper's code. Some of the results matched the paper and some did not.",
  NOT_REPRODUCED:
    "We ran this paper's code and it finished, but the result it produced does not match what the paper reports.",
  UNABLE_TO_EXECUTE:
    "We could not get this paper's code to run to completion, so there is no result to compare against the paper.",
  INCONCLUSIVE:
    "We could not reach a clear answer for this paper. The result below is not evidence either way.",
};

const VERDICT_TONE: Record<ReportData['status'], string> = {
  REPRODUCED: 'border-emerald-300 bg-emerald-50',
  PARTIALLY_REPRODUCED: 'border-amber-300 bg-amber-50',
  NOT_REPRODUCED: 'border-red-300 bg-red-50',
  UNABLE_TO_EXECUTE: 'border-[#CDC5B4] bg-[#F4F1E8]',
  INCONCLUSIVE: 'border-[#CDC5B4] bg-[#F4F1E8]',
};

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
          Loading the report...
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col items-center justify-center font-mono p-6">
        <p className="text-sm text-fail mb-4 font-bold">
          There is no report for this run yet.
        </p>
        <Link to={`/p/${id}`} className="text-xs text-rust hover:underline">
          ← Back to the run
        </Link>
      </div>
    );
  }

  // Everything below comes from the backend's verified comparison. Nothing is invented.
  //
  // A `?? 0.956` fallback here meant a run that crashed and produced no metrics displayed
  // the benchmark's expected answer as its "observed mean", with a difference of 0.0000
  // and a hardcoded pass: the page asserted a successful reproduction of a run that never
  // executed.
  const attempts = report.attempts || [];
  const claim = report.claims?.[0];
  const comparisonPoints = report.runs_summary?.comparison_chart ?? [];
  const metricKey = claim?.metric ?? claim?.result_key ?? 'metric';
  const reportedTarget = claim?.reported ?? null;
  const toleranceValue = claim?.tolerance?.value ?? null;
  const toleranceLabel =
    toleranceValue === null
      ? 'not specified'
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

  // For a custom run the backend stores benchmark_id as the literal "custom", which makes
  // a useless page title. Prefer the repository name the code actually came from.
  const repoName = report.repo_url
    ? report.repo_url.replace(/\.git$/, '').split('/').filter(Boolean).slice(-2).join('/')
    : null;
  const reportTitle =
    report.benchmark_id && report.benchmark_id !== 'custom'
      ? report.benchmark_id
      : repoName || 'Your paper';

  // Crashed attempts are omitted from the chart rather than plotted as a fabricated value.
  const chartData = comparisonPoints
    .filter((p) => p.observed !== null)
    .map((p) => ({
      name: `Run ${p.run_n}`,
      accuracy: Number(Number(p.observed).toFixed(4)),
      target: reportedTarget ?? undefined,
    }));

  const crashedRuns = comparisonPoints.filter((p) => p.observed === null);

  // The y-axis used to be hardcoded to [0, 1.15], which silently assumed every metric was
  // an accuracy between 0 and 1. A paper reporting a loss of 0.036 drew a bar one pixel
  // tall against an axis running to 1.15, so the only chart in the report showed nothing.
  // The range is derived from the values actually being plotted instead.
  const plottedMax = Math.max(
    ...chartData.map((d) => d.accuracy),
    reportedTarget ?? 0,
    Number.MIN_VALUE
  );
  const yMax = plottedMax > 0 ? Number((plottedMax * 1.35).toPrecision(3)) : 1;

  const claims = report.claims ?? [];
  const limitations = report.limitations ?? [];
  const notChecked = report.not_checked ?? [];
  const removedStatements = report.statements_removed ?? [];
  const verification = report.verification_summary ?? null;
  const unselectedClaims = report.unselected_claims ?? [];
  const appliedPatchCount =
    report.patches_summary?.length ??
    (report.patches ?? []).filter((p) => p.status === 'applied').length;
  const totalPatches = (report.patches ?? []).length;

  const narrativeGroups: Array<['findings' | 'causes' | 'fixes', string]> = [
    ['findings', 'What we found'],
    ['causes', 'Why it happened'],
    ['fixes', 'What we changed'],
  ];
  // `statements.limitations` / `.not_checked` duplicate the deterministic lists rendered in
  // the "What we did not check" section, so only the narrative sections are shown here.
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

  // Plain words rather than the raw tolerance flag. `null` stays distinct from `false`:
  // "we did not measure this" and "we measured it and it was off" are different facts.
  const statusCell = (within: boolean | null) =>
    within === true
      ? { text: 'Matched', cls: 'text-emerald-700' }
      : within === false
      ? { text: 'Did not match', cls: 'text-red-700' }
      : { text: 'Not measured', cls: 'text-amber-800' };

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
                This was a practice run.
              </span>{' '}
              The code did not run in a real container, so these numbers do not prove
              anything about the paper.
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
              <span>Back to the run</span>
            </Link>

            <h1 className="font-serif text-2xl sm:text-3xl font-normal uppercase tracking-wide text-[#1F2A44]">
              Report: {reportTitle}
            </h1>
            <p className="text-xs text-[#4A5470] font-mono">
              {attempts.length} run{attempts.length === 1 ? '' : 's'}, {report.after_n_fixes}{' '}
              fix{report.after_n_fixes === 1 ? '' : 'es'} you approved.
            </p>

            {/* Where the code and paper came from */}
            <div className="pt-2 text-[11px] text-[#4A5470] space-y-0.5 border-t border-[#CDC5B4]/60">
              <div>
                <span className="font-bold text-[#1F2A44]">Code:</span>{' '}
                <span className="font-mono">
                  {report.repo_url || report.benchmark_id || 'Built-in test case'}
                </span>
                {/* The backend writes the literal string "unknown" when no commit was
                    recorded. Rendering it as "version unknown" dresses a missing value up
                    as a value, so the chip is dropped instead. */}
                {report.repo_commit && report.repo_commit !== 'unknown' && (
                  <span className="ml-2 px-1.5 py-0.5 bg-[#EDE7DB] rounded text-[10px] text-[#1F2A44]">
                    version {report.repo_commit.slice(0, 8)}
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

        {/* ================= THE ANSWER, IN PLAIN WORDS ================= */}
        <section
          className={`rounded-xl border-2 p-6 sm:p-8 space-y-4 shadow-sm ${
            VERDICT_TONE[report.status]
          }`}
        >
          <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
            The short answer
          </span>

          <p className="font-serif text-xl sm:text-2xl leading-snug text-[#1F2A44]">
            {VERDICT_SENTENCE[report.status]}
          </p>

          {report.reason && (
            <p className="font-mono text-xs text-[#4A5470] leading-relaxed">{report.reason}</p>
          )}

          {/* The headline numbers, spelled out. Only shown when a number was measured. */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
            <div className="bg-[#FAF7F0]/80 border border-[#CDC5B4] rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-[#4A5470]">
                The paper says
              </div>
              <div className="font-mono text-lg font-bold text-[#1F2A44]">
                {fmt(reportedTarget)}
              </div>
              <div className="text-[10px] text-[#4A5470]">for {metricKey}</div>
            </div>
            <div className="bg-[#FAF7F0]/80 border border-[#CDC5B4] rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-[#4A5470]">
                We measured
              </div>
              <div className="font-mono text-lg font-bold text-[#1F2A44]">
                {observedFinal === null ? 'nothing' : fmt(observedFinal)}
              </div>
              <div className="text-[10px] text-[#4A5470]">
                {observedFinal === null ? 'the run produced no number' : 'on the last run'}
              </div>
            </div>
            <div className="bg-[#FAF7F0]/80 border border-[#CDC5B4] rounded-lg p-3">
              <div className="text-[10px] uppercase tracking-wider text-[#4A5470]">
                Difference
              </div>
              <div
                className={`font-mono text-lg font-bold ${
                  statusCell(finalPoint?.within_tolerance ?? null).cls
                }`}
              >
                {fmt(absGap)}
              </div>
              <div className="text-[10px] text-[#4A5470]">
                allowed: {toleranceLabel} → {statusCell(finalPoint?.within_tolerance ?? null).text}
              </div>
            </div>
          </div>

          <p className="font-mono text-[11px] text-[#4A5470] leading-relaxed border-t border-[#CDC5B4]/60 pt-3">
            {totalPatches === 0
              ? 'Nothing in the code was changed. It ran as the authors published it.'
              : `${appliedPatchCount} of ${totalPatches} suggested change${
                  totalPatches === 1 ? '' : 's'
                } ${appliedPatchCount === 1 ? 'was' : 'were'} applied, and you approved each one before it was. The full list is further down.`}
          </p>
        </section>

        {/* Action Toolbar */}
        <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-4 text-xs font-mono">
          <span className="text-[#4A5470]">Take this report with you</span>
          <div className="flex items-center gap-3">
            <a
              href={`/api/projects/${id}/kit`}
              download={`rerun_kit_${id}.zip`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] transition-colors uppercase tracking-wider text-[11px] font-semibold"
              title="Everything needed to repeat this run: patches, logs, results and the report"
            >
              <Package className="w-3.5 h-3.5 text-rust" />
              <span>Download everything (.zip)</span>
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
              <span>{copyError ? 'Copy failed' : copiedMd ? 'Copied' : 'Copy as text'}</span>
            </button>
            <a
              href={`/api/projects/${id}/report.md`}
              download={`rerun_report_${id}.md`}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-sm bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[#1F2A44] border border-[#CDC5B4] transition-colors uppercase tracking-wider text-[11px] font-semibold"
            >
              <FileText className="w-3.5 h-3.5 text-rust" />
              <span>Save as text (.md)</span>
            </a>
            <button
              onClick={() => window.print()}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-[#7A3317] shadow-sm active:scale-95 transition-all"
            >
              <Download className="w-3.5 h-3.5 text-[#FAF7F0]" />
              <span>Print / PDF</span>
            </button>
          </div>
        </div>

        {/* ================= 1. DID THE NUMBERS MATCH? ================= */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-6 shadow-sm font-mono text-xs text-[#1F2A44]">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1.5">
              <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
                1. The numbers
              </span>
              <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
                Did the numbers match?
              </h2>
              <p className="text-[#4A5470] font-sans text-xs">
                Each bar is one run of the code. The dashed line is the number the paper
                claims. A run is a match when its bar lands inside the paper's allowed
                margin.
              </p>
            </div>
            <div className="shrink-0 flex items-center gap-2.5 px-3.5 py-2 rounded-lg bg-[#FAF7F0] border border-[#CDC5B4] shadow-sm text-xs font-mono">
              <span className="text-[#4A5470]">Paper's number:</span>
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
                <YAxis domain={[0, yMax]} stroke="#78716C" fontSize={11} />
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
                          Paper says {fmt(reportedTarget)}
                        </text>
                      </g>
                    );
                  }}
                />
                <Bar
                  dataKey="accuracy"
                  fill="#B8572F"
                  name="What we measured"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={90}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Headline comparison */}
          <div className="overflow-x-auto pt-4 border-t border-[#CDC5B4]">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                  <th className="py-2 px-3">What was measured</th>
                  <th className="py-2 px-3">Paper says</th>
                  <th className="py-2 px-3">Allowed margin</th>
                  <th className="py-2 px-3">We measured</th>
                  <th className="py-2 px-3">Difference</th>
                  <th className="py-2 px-3">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#CDC5B4]/50">
                <tr>
                  <td className="py-2.5 px-3 font-semibold text-[#1F2A44]">{metricKey}</td>
                  <td className="py-2.5 px-3 text-amber-800 font-bold">{fmt(reportedTarget)}</td>
                  <td className="py-2.5 px-3 text-[#4A5470]">{toleranceLabel}</td>
                  <td className="py-2.5 px-3 text-rust font-bold">
                    {observedFinal === null ? 'nothing measured' : fmt(observedFinal)}
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

          {/* Every claim, not only the headline one. */}
          {claims.length > 1 && (
            <div className="overflow-x-auto pt-4 border-t border-[#CDC5B4] space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                Every claim we checked ({claims.length})
              </div>
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                    <th className="py-2 px-3">Claim</th>
                    <th className="py-2 px-3">What was measured</th>
                    <th className="py-2 px-3">Paper says</th>
                    <th className="py-2 px-3">We measured</th>
                    <th className="py-2 px-3">Difference</th>
                    <th className="py-2 px-3">Result</th>
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

          {/* Claims nobody asked us to verify. Omitting them made the report look
              like it covered the whole paper. */}
          {unselectedClaims.length > 0 && (
            <div className="pt-4 border-t border-[#CDC5B4] space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                Claims in the paper we did not check ({unselectedClaims.length})
              </div>
              <ul className="space-y-1 text-[#4A5470] list-disc list-inside leading-relaxed">
                {unselectedClaims.map((c) => (
                  <li key={c.id}>
                    <span className="font-bold text-[#1F2A44]">{c.id}</span>{' '}
                    {c.statement || c.metric}
                    {c.reported !== undefined && c.reported !== null && (
                      <span className="font-mono"> — the paper reports {c.reported}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Per-run detail, including runs that produced no number at all. */}
          {comparisonPoints.length > 0 && (
            <div className="overflow-x-auto pt-4 border-t border-[#CDC5B4]">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold pb-2">
                Run by run
              </div>
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                    <th className="py-2 px-3">Run</th>
                    <th className="py-2 px-3">Finished cleanly?</th>
                    <th className="py-2 px-3">We measured</th>
                    <th className="py-2 px-3">Result</th>
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
                          {pt.exit_code === null
                            ? 'stopped by us'
                            : pt.exit_code === 0
                            ? 'yes'
                            : `no (error code ${pt.exit_code})`}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[#1F2A44]">
                          {pt.observed === null ? 'no number produced' : fmt(pt.observed)}
                        </td>
                        <td className={`py-2.5 px-3 font-bold ${st.cls}`}>{st.text}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {crashedRuns.length > 0 && (
                <p className="pt-3 text-[11px] text-amber-800 font-mono">
                  {crashedRuns.length} run{crashedRuns.length === 1 ? '' : 's'} produced no
                  number at all. {crashedRuns.length === 1 ? 'It is' : 'They are'} left out of
                  the chart above rather than drawn as a value.
                </p>
              )}
            </div>
          )}
        </section>

        {/* ================= 2. WHAT WE CHANGED ================= */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-6 shadow-sm font-mono text-xs text-[#1F2A44]">
          <div className="space-y-1.5">
            <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
              2. The changes
            </span>
            <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
              What we changed to make it run
            </h2>
            {/* patches_summary is the backend's applied subset; the list below is every
                suggestion. Stating both stops an applied count being read off a list that
                also contains rejected and dropped changes. */}
            {totalPatches > 0 && (
              <p className="text-[#4A5470] font-sans text-xs">
                {appliedPatchCount} of {totalPatches} suggested change
                {totalPatches === 1 ? '' : 's'} {appliedPatchCount === 1 ? 'was' : 'were'}{' '}
                actually applied. Each one needed your approval first.
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
                      <span className="font-bold text-rust">{p.id || `Change ${idx + 1}`}</span>
                      <span className="px-2 py-0.5 rounded bg-[#FAF7F0] text-[#1F2A44] border border-[#CDC5B4] text-[10px] uppercase tracking-wider font-bold">
                        {p.risk_class}
                      </span>
                    </div>
                    {/* The real status. This was hardcoded "Applied & Verified", so a
                        dropped, rejected or reverted change was presented as applied. */}
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
                      {p.status === 'applied' ? 'Applied' : p.status ?? 'unknown'}
                    </span>
                  </div>

                  <p className="text-[#1F2A44] font-sans text-xs">{p.rationale}</p>

                  {p.evidence && p.evidence.length > 0 && (
                    <div className="flex items-center gap-2 pt-2 border-t border-[#CDC5B4]/50">
                      <span className="text-[#4A5470] text-[11px]">Based on:</span>
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
              Nothing had to be changed. The code reproduced the paper's result exactly as
              published.
            </p>
          ) : (
            <p className="text-[#4A5470]">
              Nothing was changed. The result is{' '}
              <span className="font-bold text-rust">{report.status}</span>
              {report.reason ? `: ${report.reason}` : ''}. An empty list of changes does not
              mean the run succeeded.
            </p>
          )}
        </section>

        {/* ================= 3. SETTINGS THAT DISAGREED ================= */}
        {report.config_diff && report.config_diff.length > 0 && (
          <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-4 shadow-sm font-mono text-xs text-[#1F2A44]">
            <div className="space-y-1.5">
              <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
                3. The settings
              </span>
              <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
                Settings that did not match the paper
              </h2>
              <p className="text-[#4A5470] font-sans text-xs">
                The paper describes how it was run. These are the places where the code
                disagreed with that description.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[11px] uppercase tracking-wider">
                    <th className="py-2 px-3">Setting</th>
                    <th className="py-2 px-3">What the code used</th>
                    <th className="py-2 px-3">What the paper says</th>
                    <th className="py-2 px-3">Result</th>
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

        {/* ================= 4. WHAT WE DID NOT CHECK ================= */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-5 shadow-sm text-xs font-mono text-[#1F2A44]">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 text-rust font-bold uppercase tracking-wider">
              <AlertTriangle className="w-4 h-4" />
              <span>4. The limits of this report</span>
            </div>
            <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
              What we did not check
            </h2>
            <p className="text-[#4A5470] font-sans text-xs">
              Everything a reader should know before relying on the answer above.
            </p>
          </div>

          {limitations.length > 0 && (
            <div className="space-y-2">
              <div className="text-[11px] uppercase tracking-wider text-[#4A5470] font-bold">
                Things that limit this result
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
                Things we did not look at
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
              This report lists no limits at all. That is unusual, and it is more likely a gap
              in the report than a sign that nothing was missed.
            </p>
          )}
        </section>

        {/* ================= 5. THE DETAIL BEHIND THE ANSWER ================= */}
        <div className="space-y-2">
          <h2 className="font-serif text-2xl uppercase tracking-wide text-[#1F2A44]">
            The detail behind the answer
          </h2>
          <p className="font-mono text-xs text-[#4A5470]">
            You do not need to read this part to use the result. It is here so the result can
            be checked.
          </p>
        </div>

        {/* 5a. Statements we removed from our own write-up */}
        {verification && (
          <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-5 shadow-sm font-mono text-xs text-[#1F2A44]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="space-y-1.5">
                <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
                  5a. Our own wording, checked
                </span>
                <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
                  Sentences we kept, and sentences we deleted
                </h2>
                <p className="text-[#4A5470] font-sans text-xs max-w-xl">
                  Every sentence written about this run has to point at a log line or a file.
                  Any sentence that could not is struck out below instead of being quietly
                  dropped.
                </p>
              </div>
              <div className="flex items-center gap-4 text-[11px]">
                <div className="text-center">
                  <div className="text-lg font-bold text-[#1F2A44]">{verification.total}</div>
                  <div className="uppercase tracking-wider text-[#4A5470]">Written</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-bold text-emerald-700">{verification.verified}</div>
                  <div className="uppercase tracking-wider text-[#4A5470]">Kept</div>
                </div>
                <div className="text-center">
                  <div
                    className={`text-lg font-bold ${
                      verification.removed > 0 ? 'text-red-700' : 'text-[#CDC5B4]'
                    }`}
                  >
                    {verification.removed}
                  </div>
                  <div className="uppercase tracking-wider text-[#4A5470]">Deleted</div>
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
                        <span className="text-[10px] text-[#4A5470]">Based on:</span>
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
                  <span>Deleted from this report ({removedStatements.length})</span>
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

        {/* 5b. Where every fact came from */}
        <section className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 sm:p-8 space-y-4 shadow-sm font-mono text-xs text-[#1F2A44]">
          <div className="space-y-1.5">
            <span className="text-rust font-bold uppercase tracking-[0.2em] text-[11px]">
              5b. The paper trail
            </span>
            <h2 className="font-serif text-xl uppercase tracking-wide text-[#1F2A44]">
              Where every fact came from
            </h2>
            <p className="text-[#4A5470] font-sans text-xs">
              Each row is a saved piece of a real file or log, with a fingerprint so you can
              tell it has not been edited since. Click any one to read it.
            </p>
          </div>
          <EvidenceLedger projectId={id || ''} onSelectEvidence={setSelectedEvidenceId} bare />
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

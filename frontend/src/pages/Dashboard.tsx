import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { NavbarApp } from '../components/layout/NavbarApp';
import { PhaseBar } from '../components/dashboard/PhaseBar';
import { BudgetBar } from '../components/dashboard/BudgetBar';
import { TracePanel } from '../components/dashboard/TracePanel';
import { Terminal } from '../components/dashboard/Terminal';
import { ReportToast } from '../components/ui/ReportToast';
import { DiffView } from '../components/dashboard/DiffView';
import { AttemptsTable } from '../components/dashboard/AttemptsTable';
import { ApprovalModal } from '../components/dashboard/ApprovalModal';
import { ProvisioningModal } from '../components/dashboard/ProvisioningModal';
import { PreflightNotices } from '../components/dashboard/PreflightNotices';
import { EvidenceLedger } from '../components/dashboard/EvidenceLedger';
import { EvidenceDrawer } from '../components/ui/EvidenceDrawer';
import { Footer } from '../components/layout/Footer';
import { useEventStream } from '../hooks/useEventStream';
import {
  fetchProjectState,
  fetchPendingApproval,
  submitApproval,
  fetchRunLog,
  approveProvisioning,
  rejectProvisioning,
} from '../api/client';
import type { ProjectStateSummary, Patch, CriticReview, Event } from '../api/types';
import { ArrowRight, FileCheck } from 'lucide-react';

export const Dashboard: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<ProjectStateSummary | null>(null);
  const [loading, setLoading] = useState(true);

  // Approval modal state
  const [isApprovalOpen, setIsApprovalOpen] = useState(false);
  const [currentApprovalId, setCurrentApprovalId] = useState<string>('');
  const [currentPatch, setCurrentPatch] = useState<Patch | null>(null);
  const [criticReview, setCriticReview] = useState<CriticReview | null>(null);
  const [approvalBanner, setApprovalBanner] = useState<string | null>(null);
  const [requiresExtraConfirm, setRequiresExtraConfirm] = useState(false);

  // Provisioning gate state. The orchestrator and the API have always had this gate; the
  // console never rendered it, so a project whose preflight proposed a provisioning plan
  // parked at PREFLIGHT with no way to approve and never progressed.
  const [isProvisioningOpen, setIsProvisioningOpen] = useState(false);

  // Evidence Drawer state
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);

  // Terminal log stream
  const [currentLogText, setCurrentLogText] = useState<string>('');

  // Surfaces the finished report to an operator who has scrolled past the banner.
  const [showReportToast, setShowReportToast] = useState(false);

  // Initial load
  const loadState = useCallback(async () => {
    if (!id) return;
    try {
      const data = await fetchProjectState(id);
      setState(data);

      // Check if pending approval is waiting
      if (data.pending?.kind === 'approval') {
        const appData = await fetchPendingApproval(id);
        setCurrentApprovalId(appData.approval_id);
        setCurrentPatch(appData.patch);
        // Latest review from the history, falling back to the single-object form.
        const latestReview =
          appData.reviews && appData.reviews.length > 0
            ? appData.reviews[appData.reviews.length - 1]
            : appData.critic_review ?? null;
        setCriticReview(latestReview);
        setApprovalBanner(appData.banner);
        // A banner always requires explicit confirmation, even if the server omits the flag.
        setRequiresExtraConfirm(Boolean(appData.requires_extra_confirm || appData.banner));
        setIsApprovalOpen(true);
      } else {
        setIsApprovalOpen(false);
      }

      setIsProvisioningOpen(data.pending?.kind === 'provisioning');

      // Load active run log
      const attemptsCount = data.attempts?.length || 0;
      if (attemptsCount > 0) {
        const log = await fetchRunLog(id, attemptsCount);
        setCurrentLogText(log);
      }
    } catch (e) {
      console.error('Failed to load project state', e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadState();
    const interval = setInterval(() => {
      setState((prev) => {
        const terminalStatuses = ['DONE', 'REPRODUCED', 'NOT_REPRODUCED', 'UNABLE_TO_EXECUTE', 'ABORTED', 'INCONCLUSIVE'];
        const isFinished = prev?.phase === 'DONE' || (prev?.status && terminalStatuses.includes(prev.status));
        if (!isFinished) {
          loadState();
        }
        return prev;
      });
    }, 2500);
    return () => clearInterval(interval);
  }, [loadState]);

  // Hook into live SSE event stream
  const handleIncomingEvent = useCallback(
    (event: Event) => {
      // If phase changes or approval requested, refresh immediately
      if (
        event.type === 'phase_changed' ||
        event.type === 'approval_requested' ||
        event.type === 'patch_applied' ||
        event.type === 'report_ready'
      ) {
        loadState();
      }
    },
    [loadState]
  );

  const { events } = useEventStream({
    projectId: id || null,
    onEvent: handleIncomingEvent,
  });

  // Offer the report the moment one exists. Gating on phase === 'DONE' meant the operator
  // waited through the optional statement-enrichment call with no way to reach the report.
  const isReportReady =
    state?.phase === 'DONE' || Boolean(state?.report_available) || Boolean(state?.final);

  /*
    Announce the report once, on the edge where it becomes available.

    `isReportReady` is also true for every later poll and on every revisit of a
    finished project, so firing off the value itself would re-toast a run that
    completed days ago. The ref records whether this mount has already seen the
    report exist: it starts null, is set on the first state that resolves it
    either way, and only a false -> true crossing raises the toast. Opening an
    already-finished project therefore stays quiet.

    This sits with the other hooks and above the loading early-return, because a
    hook after a conditional return changes the hook order between renders and
    React tears the page down.
  */
  const wasReportReady = useRef<boolean | null>(null);
  useEffect(() => {
    if (loading || !state) return;
    const previously = wasReportReady.current;
    wasReportReady.current = isReportReady;
    if (previously === false && isReportReady) setShowReportToast(true);
  }, [isReportReady, loading, state]);

  // Handle human patch approval
  const handleApprovePatch = async (comment?: string, confirmExtra?: boolean) => {
    if (!currentApprovalId || !id) return;
    try {
      await submitApproval(id, currentApprovalId, 'approve', confirmExtra, comment);
      setIsApprovalOpen(false);
      await loadState();
    } catch (e) {
      console.error('Failed to submit approval', e);
    }
  };

  // Handle human patch reject
  const handleRejectPatch = async (comment?: string) => {
    if (!currentApprovalId || !id) return;
    try {
      await submitApproval(id, currentApprovalId, 'reject', false, comment);
      setIsApprovalOpen(false);
      await loadState();
    } catch (e) {
      console.error('Failed to reject patch', e);
    }
  };

  // Handle the dependency provisioning gate
  const handleApproveProvisioning = async () => {
    if (!id) return;
    await approveProvisioning(id);
    setIsProvisioningOpen(false);
    await loadState();
  };

  const handleRejectProvisioning = async () => {
    if (!id) return;
    await rejectProvisioning(id);
    setIsProvisioningOpen(false);
    await loadState();
  };

  // Handle human patch edit (D14)
  const handleEditPatch = async (edits: any[], comment?: string) => {
    if (!currentApprovalId || !id) return;
    await submitApproval(id, currentApprovalId, 'edit', false, comment, edits);
    setIsApprovalOpen(false);
    await loadState();
  };

  if (loading && !state) {
    return (
      <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col items-center justify-center font-mono">
        <div className="w-10 h-10 border-4 border-rust border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-xs text-[#4A5470] tracking-wider uppercase font-semibold">
          Connecting to project console...
        </p>
      </div>
    );
  }

  const activePatch =
    state?.patches && state.patches.length > 0 ? state.patches[state.patches.length - 1] : null;

  return (
    <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col font-mono select-text">
      {/* App Navbar */}
      <NavbarApp
        projectId={id}
        benchmarkId={state?.benchmark_id}
        phase={state?.phase}
        status={state?.final?.status || state?.status}
        isReportReady={isReportReady}
        isReplay={events.some((e) => e.type.includes('replay'))}
      />

      {/* Phase Bar */}
      <PhaseBar currentPhase={state?.phase || 'INGEST'} />

      {/* Main Operational Console Grid */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 flex flex-col gap-6">
        {/* Blockers, warnings and unresolved issues — all recorded by the backend on every
            poll and, until now, rendered nowhere. */}
        <PreflightNotices
          preflight={state?.preflight}
          unresolvedIssues={state?.unresolved_issues}
        />

        {/* Report ready banner alert */}
        {isReportReady && (
          <div className="p-4 rounded-xl bg-[#FAF7F0] border-2 border-rust flex items-center justify-between shadow-md">
            <div className="flex items-center gap-3">
              <FileCheck className="w-5 h-5 text-rust" />
              <div>
                <h4 className="text-sm font-bold text-[#1F2A44] font-mono uppercase tracking-wide">
                  Reproduction Complete · Verdict:{' '}
                  <span className="text-rust">{state?.final?.status || state?.status}</span>
                </h4>
                <p className="text-xs text-[#4A5470]">
                  All verification runs, audits, and patches are finalized. Read the complete
                  certified report.
                </p>
              </div>
            </div>

            <button
              onClick={() => navigate(`/p/${id}/report`)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-[#7A3317] shadow-md active:scale-95 transition-all"
            >
              <span>View Report</span>
              <ArrowRight className="w-4 h-4 stroke-[3] text-[#FAF7F0]" />
            </button>
          </div>
        )}

        {showReportToast && (
          <ReportToast
            status={state?.final?.status || state?.status}
            onOpen={() => {
              setShowReportToast(false);
              navigate(`/p/${id}/report`);
            }}
            onDismiss={() => setShowReportToast(false)}
          />
        )}

        {/* Middle 3-Column Work Desk: Trace | Terminal | Diff */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[500px] min-h-0">
          {/* Col 1: Trace Panel */}
          <div className="h-full min-h-0 flex flex-col overflow-hidden">
            <TracePanel
              events={events}
              onSelectEvidence={(eid) => setSelectedEvidenceId(eid)}
            />
          </div>

          {/* Col 2: Terminal Logs */}
          <div className="h-full min-h-0 flex flex-col overflow-hidden">
            <Terminal
              projectId={id || ''}
              totalAttempts={state?.attempts?.length || 0}
              currentLogText={currentLogText}
            />
          </div>

          {/* Col 3: Patch / Diff Panel */}
          <div className="h-full min-h-0 flex flex-col overflow-hidden">
            <DiffView patch={activePatch} />
          </div>
        </div>

        {/* Bottom Section: Attempts Table & Budget Counters */}
        <div className="space-y-4 pb-8">
          <BudgetBar budgets={state?.budgets} />
          <AttemptsTable attempts={state?.attempts || []} claims={state?.claims} />
          <EvidenceLedger projectId={id || ''} onSelectEvidence={setSelectedEvidenceId} />
        </div>
      </main>

      {/* Persistent Kraft Footer */}
      <Footer />

      {/* Approval Modal (Pop-up on pending approval) */}
      {currentPatch && (
        <ApprovalModal
          isOpen={isApprovalOpen}
          approvalId={currentApprovalId}
          patch={currentPatch}
          criticReview={criticReview}
          banner={approvalBanner}
          requiresExtraConfirm={requiresExtraConfirm}
          onApprove={handleApprovePatch}
          onReject={handleRejectPatch}
          onEdit={handleEditPatch}
          onSelectEvidence={(eid) => setSelectedEvidenceId(eid)}
        />
      )}

      {/* Dependency Provisioning Gate */}
      <ProvisioningModal
        isOpen={isProvisioningOpen}
        packages={state?.pending?.packages || []}
        details={state?.pending?.details}
        pythonImage={state?.pending?.python_image}
        warnings={state?.pending?.warnings}
        onApprove={handleApproveProvisioning}
        onReject={handleRejectProvisioning}
      />

      {/* Slide-over Evidence Drawer */}
      <EvidenceDrawer
        projectId={id || ''}
        evidenceId={selectedEvidenceId}
        onClose={() => setSelectedEvidenceId(null)}
      />
    </div>
  );
};

export default Dashboard;

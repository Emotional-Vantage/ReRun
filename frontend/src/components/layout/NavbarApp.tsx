import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { LayoutDashboard, FileCheck2, AlertOctagon, Power, Plus } from 'lucide-react';
import { abortProject, killSwitch } from '../../api/client';

interface NavbarAppProps {
  projectId?: string;
  benchmarkId?: string | null;
  phase?: string;
  status?: string;
  isReportReady?: boolean;
  isReplay?: boolean;
}

export const NavbarApp: React.FC<NavbarAppProps> = ({
  projectId,
  benchmarkId,
  phase = 'INGEST',
  isReportReady = false,
  isReplay = false,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isAborting, setIsAborting] = useState(false);
  const [showConfirmAbort, setShowConfirmAbort] = useState(false);
  const [showConfirmKill, setShowConfirmKill] = useState(false);
  const [isKilling, setIsKilling] = useState(false);
  const [killError, setKillError] = useState<string | null>(null);

  const isDashboardActive = projectId ? location.pathname === `/p/${projectId}` : false;
  const isReportActive = projectId ? location.pathname === `/p/${projectId}/report` : false;

  const handleKillSwitch = async () => {
    setIsKilling(true);
    setKillError(null);
    try {
      await killSwitch();
      setShowConfirmKill(false);
      window.location.reload();
    } catch (err: any) {
      setKillError(err?.message || 'Kill switch failed');
    } finally {
      setIsKilling(false);
    }
  };

  const handleAbort = async () => {
    if (!projectId) return;
    setIsAborting(true);
    try {
      await abortProject(projectId);
      setShowConfirmAbort(false);
    } catch (e) {
      console.error(e);
    } finally {
      setIsAborting(false);
    }
  };

  return (
    <header className="no-print sticky top-0 z-40 w-full bg-[#E5DFD3] border-b border-[#CDC5B4] text-[#1F2A44] shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
        {/* Left: Brand & Home Link */}
        <div className="flex items-center gap-4">
          <Link to="/" className="flex items-center gap-2.5 group">
            <svg
              viewBox="0 0 24 24"
              className="w-5 h-5 stroke-rust fill-none group-hover:scale-105 transition-transform"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M4 18 L10 6 L15 14 L18 10 L22 18 Z" />
              <path d="M6 13 C9 7, 18 6, 20 13 C21 17, 16 20, 12 17" strokeDasharray="2 2" />
            </svg>
            <span className="font-mono text-sm font-bold tracking-[0.22em] text-[#1F2A44] uppercase">
              RERUN
            </span>
          </Link>
          <Link
            to="/"
            className="text-xs font-mono text-[#4A5470] hover:text-[#1F2A44] transition-colors px-2.5 py-1 rounded border border-[#CDC5B4] bg-[#FAF7F0] hover:bg-[#F4F1E8]"
          >
            ← Field Notebook
          </Link>
        </div>

        {/* Center: Project Chip, Phase, & View Tabs */}
        {projectId && (
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded bg-[#FAF7F0] border border-[#CDC5B4] text-xs font-mono shadow-sm">
              <span className="text-rust font-bold">{benchmarkId || 'case'}</span>
              <span className="text-[#CDC5B4]">•</span>
              <span className="text-[#4A5470]">{projectId.slice(0, 10)}</span>
            </div>

            <Link
              to="/new"
              className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#FAF7F0] hover:bg-[#F4F1E8] border border-[#CDC5B4] hover:border-rust text-xs font-mono text-[#1F2A44] hover:text-rust font-bold transition-all shadow-sm active:scale-95"
              title="Start a new reproduction run (Benchmark Cases or Custom Paper)"
            >
              <Plus className="w-3.5 h-3.5 text-rust stroke-[2.5]" />
              <span>New Run</span>
            </Link>

            <div className="flex items-center bg-[#D9D4C6] rounded-lg p-0.5 border border-[#CDC5B4] text-xs font-medium">
              <button
                onClick={() => navigate(`/p/${projectId}`)}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all ${
                  isDashboardActive
                    ? 'bg-[#FAF7F0] text-[#1F2A44] font-bold shadow-sm'
                    : 'text-[#4A5470] hover:text-[#1F2A44]'
                }`}
              >
                <LayoutDashboard className="w-3.5 h-3.5" />
                <span>Console</span>
              </button>
              <button
                onClick={() => isReportReady && navigate(`/p/${projectId}/report`)}
                disabled={!isReportReady}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-md transition-all ${
                  isReportActive
                    ? 'bg-[#FAF7F0] text-[#1F2A44] font-bold shadow-sm'
                    : isReportReady
                    ? 'text-[#4A5470] hover:text-[#1F2A44]'
                    : 'text-[#CDC5B4] cursor-not-allowed'
                }`}
                title={isReportReady ? 'View report' : 'Report ready upon completion'}
              >
                <FileCheck2 className="w-3.5 h-3.5" />
                <span>Report</span>
              </button>
            </div>
          </div>
        )}

        {/* Right: Health, Banner & Abort */}
        <div className="flex items-center gap-3">
          {isReplay && (
            <span className="px-2 py-0.5 rounded bg-purple-100 border border-purple-400 text-purple-800 text-[11px] font-mono font-bold tracking-wider uppercase animate-pulse">
              REPLAY
            </span>
          )}

          <button
            onClick={() => setShowConfirmKill(true)}
            className="flex items-center gap-1 px-2.5 py-1 rounded bg-red-600 hover:bg-red-700 text-white border border-red-800 text-xs font-mono font-bold uppercase tracking-wider transition-colors shadow-sm"
            title="Stop every running project and kill all sandbox containers"
          >
            <Power className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Stop All</span>
          </button>

          {projectId && phase !== 'DONE' && (
            <button
              onClick={() => setShowConfirmAbort(true)}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-[#FAF7F0] hover:bg-red-50 text-red-600 border border-red-300 hover:border-red-400 text-xs font-mono transition-colors shadow-sm"
              title="Abort current execution"
            >
              <AlertOctagon className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Abort</span>
            </button>
          )}
        </div>
      </div>

      {/* Global kill-switch confirmation */}
      {showConfirmKill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#FAF7F0] border-2 border-red-400 rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl space-y-4 text-[#1F2A44] font-mono">
            <h3 className="text-base font-serif uppercase tracking-wide text-red-800 font-bold">
              Stop Everything?
            </h3>
            <p className="text-xs text-[#4A5470] leading-relaxed font-sans">
              This terminates <strong>every running project</strong>, not just this one, and
              kills all sandbox containers. Projects stop where they are and can be resumed
              from their last saved state.
            </p>
            {killError && (
              <p className="text-xs text-red-700 font-bold">{killError}</p>
            )}
            <div className="flex items-center justify-end gap-3 pt-2 font-mono">
              <button
                onClick={() => { setShowConfirmKill(false); setKillError(null); }}
                className="px-3.5 py-1.5 rounded-lg text-xs text-[#4A5470] hover:bg-[#E5DFD3] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleKillSwitch}
                disabled={isKilling}
                className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-bold text-xs uppercase tracking-wider transition-colors shadow-sm disabled:opacity-60"
              >
                {isKilling ? 'Stopping…' : 'Stop All Projects'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Abort confirmation dialog */}
      {showConfirmAbort && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl space-y-4 text-[#1F2A44] font-mono">
            <h3 className="text-base font-serif uppercase tracking-wide text-[#1F2A44] font-bold">
              Abort Reproduction Run?
            </h3>
            <p className="text-xs text-[#4A5470] leading-relaxed font-sans">
              This will safely stop the sandbox container and freeze the current verification state.
            </p>
            <div className="flex items-center justify-end gap-3 pt-2 font-mono">
              <button
                onClick={() => setShowConfirmAbort(false)}
                className="px-3.5 py-1.5 rounded-lg text-xs text-[#4A5470] hover:bg-[#E5DFD3] transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleAbort}
                disabled={isAborting}
                className="px-3.5 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white font-bold text-xs uppercase tracking-wider transition-colors shadow-sm"
              >
                {isAborting ? 'Aborting...' : 'Confirm Abort'}
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

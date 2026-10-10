import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  CheckCircle2,
  Copy,
  Check,
  Send,
  RotateCcw,
  UploadCloud,
  FileText,
  GitBranch,
  Code,
  AlertTriangle,
  Layers,
  Search,
} from 'lucide-react';
import { NavbarApp } from '../components/layout/NavbarApp';
import { Footer } from '../components/layout/Footer';
import {
  fetchBenchmarks,
  createProject,
  createCustomProject,
  startProject,
  fetchClaimsDraft,
  confirmClaims,
  rejectClaims,
  fetchProjectState,
  fetchTriageReport,
} from '../api/client';
import type { BenchmarkCase, Claim } from '../api/types';

const GITHUB_REPO_REGEX = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+(\.git)?$/;
const MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB

export const NewProject: React.FC = () => {
  const navigate = useNavigate();

  // Mode: benchmark vs custom
  const [sourceMode, setSourceMode] = useState<'benchmark' | 'custom'>('benchmark');

  // Step: 1 = choose/upload, 2 = confirm claims
  const [step, setStep] = useState<1 | 2>(1);

  // Benchmarks list & selection
  const [cases, setCases] = useState<BenchmarkCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('b4_combined');
  const [allowHighRisk, setAllowHighRisk] = useState<boolean>(false);
  const [loadingCases, setLoadingCases] = useState<boolean>(true);

  // Custom Repo & PDF state
  const [repoUrl, setRepoUrl] = useState<string>('');
  const [repoRef, setRepoRef] = useState<string>('');
  const [paperFile, setPaperFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Validation & Error states
  const [urlError, setUrlError] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [generalError, setGeneralError] = useState<string | null>(null);

  // Progress state during custom ingest
  const [progressState, setProgressState] = useState<string>('');

  // Active Project & Claim draft state
  const [projectId, setProjectId] = useState<string | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [paperSettings, setPaperSettings] = useState<any[]>([]);
  // Empty by default. Prefilling this with an invented command ('python train.py --config
  // configs/default.yaml') meant any repository without that exact layout was rejected by
  // the server with "Target script 'train.py' not found in workspace", and because the
  // error was swallowed the launch button simply appeared to do nothing.
  const [runCommand, setRunCommand] = useState<string>('');
  const [commandCandidates, setCommandCandidates] = useState<string[]>([]);
  const [extractionIssues, setExtractionIssues] = useState<string[]>([]);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [triageReport, setTriageReport] = useState<any | null>(null);
  const [loadingClaims, setLoadingClaims] = useState<boolean>(false);
  const [submittingConfirm, setSubmittingConfirm] = useState<boolean>(false);
  const [copiedCmd, setCopiedCmd] = useState<boolean>(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState<boolean>(false);

  useEffect(() => {
    fetchBenchmarks()
      .then((data) => {
        setCases(data);
        if (data.length > 0) {
          const b4 = data.find((c) => c.id === 'b4_combined');
          setSelectedCaseId(b4 ? b4.id : data[0].id);
        }
      })
      .catch((err) => console.error('Failed to load benchmarks', err))
      .finally(() => setLoadingCases(false));
  }, []);

  // Client-side URL validation
  const validateUrl = (url: string): boolean => {
    const trimmed = url.trim();
    if (!trimmed) {
      setUrlError('GitHub repository URL is required.');
      return false;
    }
    if (trimmed.startsWith('file://')) {
      setUrlError('file:// URLs are strictly prohibited.');
      return false;
    }
    if (trimmed.startsWith('git@') || trimmed.startsWith('ssh://')) {
      setUrlError('SSH URLs are not supported. Use HTTPS.');
      return false;
    }
    if (trimmed.includes('@')) {
      setUrlError('Repository URL must not contain credentials or tokens.');
      return false;
    }
    if (!trimmed.startsWith('https://')) {
      setUrlError('Repository URL must start with https://');
      return false;
    }
    if (!GITHUB_REPO_REGEX.test(trimmed)) {
      setUrlError(
        'Invalid repository URL. Must be a public GitHub URL (https://github.com/owner/repo)'
      );
      return false;
    }
    setUrlError(null);
    return true;
  };

  // Client-side PDF file validation
  const validatePdf = (file: File | null): boolean => {
    if (!file) {
      setPdfError('A research paper PDF file is required.');
      return false;
    }
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setPdfError('File must be a PDF document (.pdf).');
      return false;
    }
    if (file.size > MAX_PDF_SIZE_BYTES) {
      setPdfError(
        `PDF size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds 25 MB limit.`
      );
      return false;
    }
    setPdfError(null);
    return true;
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validatePdf(file)) {
        setPaperFile(file);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validatePdf(file)) {
        setPaperFile(file);
      }
    }
  };

  // Start project flow (Benchmark or Custom)
  const handleStartProject = async () => {
    setGeneralError(null);

    let newProjId = '';

    if (sourceMode === 'custom') {
      const urlValid = validateUrl(repoUrl);
      const pdfValid = validatePdf(paperFile);
      if (!urlValid || !pdfValid || !paperFile) {
        return;
      }

      setLoadingClaims(true);
      setStep(2);
      setProgressState('Cloning repository into isolated workspace...');

      try {
        // 1. Create custom project
        const res = await createCustomProject(
          repoUrl.trim(),
          paperFile,
          repoRef.trim() || undefined,
          allowHighRisk
        );
        newProjId = res.project_id;
        setProjectId(newProjId);

        // 2. Start worker
        setProgressState('Extracting paper text & citations...');
        await startProject(newProjId);

        // 3. Poll until CLAIMS_CONFIRM phase reached. The draft does not exist until the
        //    worker has ingested the repository and read the paper, so asking for it
        //    earlier returns nothing to confirm.
        setProgressState('Inspecting repository profile & extracting claims...');
        for (let i = 0; i < 45; i++) {
          await new Promise((r) => setTimeout(r, 800));
          const state = await fetchProjectState(newProjId);
          if (state.phase === 'CLAIMS_CONFIRM') {
            break;
          }
        }

        // 4. Fetch claims draft
        const draft = await fetchClaimsDraft(newProjId);
        if (draft.claims && draft.claims.length > 0) {
          setClaims(draft.claims);
        } else {
          // No claim survived verbatim-quote verification against the paper. Substituting
          // a placeholder claim carrying an invented reported value let the operator
          // confirm it as if it came from the paper. Show nothing instead and say why.
          setClaims([]);
        }
        setPaperSettings(draft.paper_settings || []);
        const candidates = draft.command_candidates || [];
        setCommandCandidates(candidates);
        setExtractionIssues(draft.extraction_issues || []);
        // Prefer a planned command, else a real candidate discovered in the repository.
        // Never invent one.
        setRunCommand(draft.command || candidates[0] || '');
        try {
          const tr = await fetchTriageReport(newProjId);
          setTriageReport(tr);
        } catch (e) {
          console.warn('Triage report fetch error', e);
        }
      } catch (err: any) {
        console.error('Failed to create custom reproduction', err);
        setGeneralError(err.message || 'Failed to initialize reproduction project.');
        setStep(1);
      } finally {
        setLoadingClaims(false);
        setProgressState('');
      }
    } else {
      // Benchmark Mode
      if (!selectedCaseId) return;
      setLoadingClaims(true);
      setStep(2);
      setProgressState('Initializing benchmark workspace...');

      try {
        const { project_id } = await createProject(selectedCaseId, allowHighRisk);
        newProjId = project_id;
        setProjectId(newProjId);

        await startProject(newProjId);

        for (let i = 0; i < 30; i++) {
          await new Promise((r) => setTimeout(r, 600));
          const state = await fetchProjectState(newProjId);
          if (state.phase === 'CLAIMS_CONFIRM') {
            break;
          }
        }

        const draft = await fetchClaimsDraft(newProjId);
        if (draft.claims && draft.claims.length > 0) {
          setClaims(draft.claims);
        } else {
          setClaims([]);
        }
        setPaperSettings(draft.paper_settings || []);
        const candidates = draft.command_candidates || [];
        setCommandCandidates(candidates);
        setExtractionIssues(draft.extraction_issues || []);
        setRunCommand(draft.command || candidates[0] || '');
        try {
          const tr = await fetchTriageReport(newProjId);
          setTriageReport(tr);
        } catch (e) {
          console.warn('Triage report fetch error', e);
        }
      } catch (err: any) {
        console.error('Failed to start reproduction flow', err);
        setGeneralError(err.message || 'Failed to start reproduction flow.');
        setStep(1);
      } finally {
        setLoadingClaims(false);
        setProgressState('');
      }
    }
  };

  // A triage verdict that reports blockers means the planned command cannot execute in the
  // sandbox: a notebook-only repository has no runnable script, a repository with missing
  // local modules or syntax errors cannot import, and a hard GPU requirement cannot be met.
  // Launching anyway only produces a guaranteed UNABLE_TO_EXECUTE, so the launch is blocked
  // and the reason is shown. "Triage Only" remains available.
  const TRIAGE_BLOCKING_VERDICTS = [
    'UNSUPPORTED_FORMAT',
    'INCOMPLETE_REPO',
    'NEEDS_GPU',
    'NEEDS_LARGE_RESOURCES',
  ];
  const triageBlockers: string[] = triageReport?.blockers ?? [];
  const isTriageBlocked = Boolean(
    triageReport &&
      (TRIAGE_BLOCKING_VERDICTS.includes(triageReport.verdict) || triageBlockers.length > 0)
  );
  const triageBlockReason: string =
    triageReport?.reason || (triageBlockers.length ? triageBlockers.join(', ') : '');

  // Adds an operator-supplied claim.
  //
  // Extraction only accepts a claim whose quote appears verbatim in the paper, which is the
  // right rule: it is what stops a hallucinated number being verified. But when every
  // candidate is rejected there has to be a way forward, otherwise the gate is a dead end.
  // A claim added here is recorded as operator-supplied, not as verified from the paper, so
  // the distinction survives into the report. Its fields start empty: a prefilled statement
  // or metric would be the console inventing the claim it is asking the operator to supply.
  const handleAddClaim = () => {
    setConfirmError(null);
    setClaims((prev) => [
      ...prev,
      {
        id: `C-${prev.length + 1}`,
        statement: '',
        metric: '',
        reported: 0,
        tolerance: { type: 'abs', value: 0.01 },
        result_key: '',
        source_ref: 'operator-supplied',
        source_quote: '',
        quote_verified: false,
        verified_in_paper: false,
        primary: prev.length === 0,
        selected: true,
        confirmed_by_human: false,
      } as Claim,
    ]);
  };

  const handleRemoveClaim = (idx: number) => {
    setClaims((prev) => prev.filter((_, i) => i !== idx));
  };

  // Step 2 Confirm Claims
  const handleConfirmClaims = async () => {
    if (!projectId) return;
    setConfirmError(null);

    if (isTriageBlocked) {
      setConfirmError(
        `Cannot launch: triage reported ${triageReport?.verdict}. ${triageBlockReason}`
      );
      return;
    }
    if (!runCommand.trim()) {
      setConfirmError('Enter the command that runs the experiment before launching.');
      return;
    }
    if (claims.length === 0) {
      setConfirmError(
        'No claim to verify. Use "Add a claim manually" to enter the metric and the value ' +
          'the paper reports, or stop at triage.'
      );
      return;
    }
    const incomplete = claims.find(
      (c) => !String(c.metric || c.result_key || '').trim() || !Number.isFinite(Number(c.reported))
    );
    if (incomplete) {
      setConfirmError(
        `Claim ${incomplete.id} is incomplete. Give it a metric key and the numeric value the ` +
          'paper reports.'
      );
      return;
    }

    setSubmittingConfirm(true);
    try {
      const confirmedClaims = claims.map((c) => ({
        ...c,
        confirmed_by_human: true,
      }));
      await confirmClaims(projectId, confirmedClaims, runCommand, allowHighRisk);
      navigate(`/p/${projectId}`);
    } catch (err: any) {
      // The server's reason must reach the operator. Swallowing it here is why the launch
      // button looked inert when the command did not exist in the repository.
      const message = err?.message || 'Failed to confirm claims.';
      console.error('Failed to confirm claims', err);
      setConfirmError(message);
    } finally {
      setSubmittingConfirm(false);
    }
  };

  // Step 2 Reject Claims
  const handleRejectClaims = async () => {
    if (!projectId) return;
    try {
      await rejectClaims(projectId);
      navigate(`/p/${projectId}`);
    } catch (err) {
      console.error('Failed to reject claims', err);
    }
  };

  const handleCopyCommand = () => {
    navigator.clipboard.writeText(runCommand);
    setCopiedCmd(true);
    setTimeout(() => setCopiedCmd(false), 2000);
  };

  return (
    <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col font-mono selection:bg-rust/20 selection:text-ink">
      <NavbarApp />

      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-10 space-y-8">
        {/* Top Stepper Indicator */}
        <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-5">
          <div className="space-y-1">
            <span className="text-xs font-mono text-rust uppercase tracking-[0.25em] font-bold">
              NEW REPRODUCTION RUN
            </span>
            <h1 className="font-serif text-2xl sm:text-3xl font-normal uppercase tracking-wide text-[#1F2A44]">
              {step === 1 ? '1. Select Source & Artifacts' : '2. Confirm Extracted Claims'}
            </h1>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs">
            <span
              className={`px-3.5 py-1.5 rounded-sm border uppercase tracking-wider ${
                step === 1
                  ? 'bg-[#FAF7F0] text-[#1F2A44] font-bold border-[#CDC5B4] shadow-sm'
                  : 'bg-[#D9D4C6] text-[#4A5470] border-[#CDC5B4]'
              }`}
            >
              1. Source Selection
            </span>
            <span className="text-[#CDC5B4]">→</span>
            <span
              className={`px-3.5 py-1.5 rounded-sm border uppercase tracking-wider ${
                step === 2
                  ? 'bg-[#FAF7F0] text-[#1F2A44] font-bold border-[#CDC5B4] shadow-sm'
                  : 'bg-[#D9D4C6] text-[#4A5470] border-[#CDC5B4]'
              }`}
            >
              2. Claim Confirmation
            </span>
          </div>
        </div>

        {/* Global Error Banner */}
        {generalError && (
          <div className="bg-red-50 border-l-4 border-fail p-4 rounded-r-lg border border-red-200 text-xs font-mono text-fail flex items-start gap-3 shadow-sm">
            <AlertTriangle className="w-5 h-5 shrink-0 text-fail" />
            <div className="space-y-1">
              <span className="font-bold uppercase tracking-wider block">Reproduction Error</span>
              <p className="font-sans leading-relaxed">{generalError}</p>
            </div>
          </div>
        )}

        {/* STEP 1: SOURCE SELECTION */}
        {step === 1 && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
            {/* Left 2 Cols: Mode Switch & Input Cards */}
            <div className="lg:col-span-2 space-y-6">
              {/* Mode Switch Tabs */}
              <div className="flex rounded-lg border border-[#CDC5B4] bg-[#D9D4C6] p-1 font-mono text-xs">
                <button
                  type="button"
                  onClick={() => setSourceMode('benchmark')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md transition-all font-bold uppercase tracking-wider ${
                    sourceMode === 'benchmark'
                      ? 'bg-[#FAF7F0] text-rust shadow-sm border border-[#CDC5B4]'
                      : 'text-[#4A5470] hover:text-[#1F2A44]'
                  }`}
                >
                  <Layers className="w-4 h-4" />
                  <span>Benchmark Cases</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSourceMode('custom')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-md transition-all font-bold uppercase tracking-wider ${
                    sourceMode === 'custom'
                      ? 'bg-[#FAF7F0] text-rust shadow-sm border border-[#CDC5B4]'
                      : 'text-[#4A5470] hover:text-[#1F2A44]'
                  }`}
                >
                  <Code className="w-4 h-4" />
                  <span>My Paper + GitHub Repo</span>
                </button>
              </div>

              {/* Mode A: Benchmark Selector */}
              {sourceMode === 'benchmark' && (
                <div className="space-y-4">
                  <span className="text-xs font-mono text-[#4A5470] uppercase tracking-[0.2em] font-bold block">
                    Choose a Synthetic Research Benchmark:
                  </span>

                  {loadingCases ? (
                    <div className="space-y-3">
                      {[1, 2, 3, 4, 5].map((i) => (
                        <div
                          key={i}
                          className="h-24 bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl animate-pulse"
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {cases.map((c) => {
                        const isSelected = selectedCaseId === c.id;
                        const isDemo = c.id === 'b4_combined';

                        return (
                          <div
                            key={c.id}
                            onClick={() => setSelectedCaseId(c.id)}
                            className={`p-5 rounded-xl border cursor-pointer transition-all ${
                              isSelected
                                ? 'bg-[#FFFFFF] border-2 border-rust shadow-[0_4px_20px_rgba(184,87,47,0.2)] ring-1 ring-rust/50'
                                : 'bg-[#FAF7F0] border-[#CDC5B4] hover:border-rust/40 hover:bg-[#FFFFFF]'
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="space-y-1">
                                <div className="flex items-center gap-2.5">
                                  <span className="font-mono text-xs font-bold text-rust">
                                    {c.id}
                                  </span>
                                  <h3 className="font-serif text-lg font-normal uppercase text-[#1F2A44]">
                                    {c.title}
                                  </h3>
                                  {isDemo && (
                                    <span className="px-2 py-0.5 rounded-sm bg-rust text-[#FAF7F0] font-mono text-[10px] font-bold uppercase tracking-wider shadow-sm">
                                      Recommended for Demo
                                    </span>
                                  )}
                                </div>
                                <p className="text-xs text-[#4A5470] font-sans leading-relaxed">
                                  {c.description}
                                </p>
                              </div>

                              <div
                                className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 ${
                                  isSelected
                                    ? 'border-rust bg-rust text-[#FAF7F0]'
                                    : 'border-[#CDC5B4] bg-[#FAF7F0]'
                                }`}
                              >
                                {isSelected && (
                                  <CheckCircle2 className="w-4 h-4 fill-current stroke-[#FAF7F0]" />
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Mode B: Custom GitHub Repo + PDF Upload */}
              {sourceMode === 'custom' && (
                <div className="space-y-6">
                  {/* Consent Notice Banner */}
                  <div className="bg-[#FAF7F0] border-l-4 border-rust p-4 rounded-r-xl border border-[#CDC5B4] text-xs font-mono text-[#1F2A44] space-y-1.5 shadow-sm">
                    <div className="flex items-center gap-2 text-rust font-bold uppercase tracking-wider text-[11px]">
                      <AlertTriangle className="w-4 h-4" />
                      <span>Security & LLM Provider Consent</span>
                    </div>
                    <p className="text-[#4A5470] font-sans leading-relaxed">
                      This runs third-party code in a sandbox; Docker is not a perfect boundary.
                      Your paper is sent to an LLM provider.
                    </p>
                  </div>

                  <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 space-y-5 shadow-sm">
                    {/* GitHub Repo URL */}
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider text-[#1F2A44] flex items-center gap-2">
                        <Code className="w-4 h-4 text-rust" />
                        <span>GitHub Repository URL:</span>
                      </label>
                      <input
                        type="url"
                        value={repoUrl}
                        onChange={(e) => {
                          setRepoUrl(e.target.value);
                          if (urlError) validateUrl(e.target.value);
                        }}
                        placeholder="https://github.com/owner/repository"
                        className={`w-full bg-[#FFFFFF] text-[#1F2A44] font-mono text-xs rounded-lg px-4 py-3 border ${
                          urlError ? 'border-fail ring-1 ring-fail' : 'border-[#CDC5B4] focus:border-rust'
                        } focus:outline-none shadow-inner`}
                      />
                      {urlError ? (
                        <p className="text-[11px] text-fail font-sans">{urlError}</p>
                      ) : (
                        <p className="text-[11px] text-[#4A5470] font-sans">
                          Must be a public HTTPS GitHub repository without credentials.
                        </p>
                      )}
                    </div>

                    {/* Git Ref / Branch (Optional) */}
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider text-[#1F2A44] flex items-center gap-2">
                        <GitBranch className="w-4 h-4 text-rust" />
                        <span>Git Branch / Commit Ref (Optional):</span>
                      </label>
                      <input
                        type="text"
                        value={repoRef}
                        onChange={(e) => setRepoRef(e.target.value)}
                        placeholder="main (or commit SHA / tag)"
                        className="w-full bg-[#FFFFFF] text-[#1F2A44] font-mono text-xs rounded-lg px-4 py-3 border border-[#CDC5B4] focus:outline-none focus:border-rust shadow-inner"
                      />
                      <p className="text-[11px] text-[#4A5470] font-sans">
                        Defaults to default branch if left empty.
                      </p>
                    </div>

                    {/* Paper PDF Dropzone */}
                    <div className="space-y-2">
                      <label className="text-xs font-bold uppercase tracking-wider text-[#1F2A44] flex items-center gap-2">
                        <FileText className="w-4 h-4 text-rust" />
                        <span>Research Paper PDF (Max 25 MB, ≤ 60 Pages):</span>
                      </label>

                      <div
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragActive(true);
                        }}
                        onDragLeave={() => setDragActive(false)}
                        onDrop={handleFileDrop}
                        onClick={() => fileInputRef.current?.click()}
                        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
                          dragActive
                            ? 'border-rust bg-rust/10'
                            : paperFile
                            ? 'border-ok/60 bg-emerald-50/50'
                            : 'border-[#CDC5B4] bg-[#FFFFFF] hover:border-rust/60 hover:bg-[#FAF7F0]'
                        }`}
                      >
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="application/pdf,.pdf"
                          onChange={handleFileChange}
                          className="hidden"
                        />

                        {paperFile ? (
                          <div className="space-y-2">
                            <div className="w-10 h-10 rounded-full bg-emerald-100 text-ok flex items-center justify-center mx-auto">
                              <CheckCircle2 className="w-6 h-6 text-emerald-600" />
                            </div>
                            <div className="space-y-1">
                              <p className="font-bold text-xs text-[#1F2A44]">{paperFile.name}</p>
                              <p className="text-[11px] text-[#4A5470]">
                                {(paperFile.size / (1024 * 1024)).toFixed(2)} MB · Click to replace
                                file
                              </p>
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-2">
                            <UploadCloud className="w-8 h-8 text-rust/70 mx-auto" />
                            <div className="space-y-1">
                              <p className="text-xs font-bold text-[#1F2A44]">
                                Drop your research paper PDF here, or{' '}
                                <span className="text-rust underline">browse</span>
                              </p>
                              <p className="text-[11px] text-[#4A5470]">
                                Must contain extractable digital text (not a scanned image)
                              </p>
                            </div>
                          </div>
                        )}
                      </div>

                      {pdfError && <p className="text-[11px] text-fail font-sans">{pdfError}</p>}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right 1 Col: What Will Happen & Launch Card */}
            <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 space-y-6 shadow-md sticky top-24 font-mono text-xs text-[#1F2A44]">
              <div className="space-y-1.5">
                <span className="text-[11px] text-rust uppercase tracking-[0.25em] font-bold block">
                  Execution Safety Guarantees
                </span>
                <h3 className="font-serif text-lg uppercase text-[#1F2A44]">What will happen:</h3>
              </div>

              {/* Mini 4-step sequence */}
              <div className="space-y-3 text-[#4A5470] leading-relaxed">
                <div className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">1.</span>
                  <span>
                    {sourceMode === 'custom'
                      ? 'Safely clone shallow repo & validate paper PDF'
                      : 'Read paper PDF & extract headline accuracy claim'}
                  </span>
                </div>
                <div className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">2.</span>
                  <span>Human operator confirms or edits claims & command</span>
                </div>
                <div className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">3.</span>
                  <span>Run code in isolated container (no network access)</span>
                </div>
                <div className="flex items-start gap-2.5">
                  <span className="text-rust font-bold">4.</span>
                  <span>Review proposed patches & approve before applying</span>
                </div>
              </div>

              {/* High risk toggle */}
              <label className="flex items-start gap-2.5 pt-4 border-t border-[#CDC5B4] text-[#4A5470] cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={allowHighRisk}
                  onChange={(e) => setAllowHighRisk(e.target.checked)}
                  className="mt-0.5 rounded accent-rust focus:ring-rust"
                />
                <span className="text-[11px] leading-relaxed">
                  Allow high-risk operations (Relax policy limits; not recommended).
                </span>
              </label>

              {/* Start Button: Tactile Rust Button */}
              <button
                type="button"
                onClick={handleStartProject}
                disabled={sourceMode === 'benchmark' ? !selectedCaseId : !repoUrl || !paperFile}
                className="w-full flex items-center justify-center gap-2 py-3.5 bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-[0.2em] shadow-xl hover:-translate-y-0.5 active:scale-95 transition-all border border-l-4 border-l-[#7A3317] disabled:opacity-40"
                style={{
                  clipPath:
                    'polygon(0% 3px, 2px 0%, calc(100% - 3px) 0%, 100% 2px, 99% calc(100% - 2px), calc(100% - 2px) 100%, 2px 99%, 0% calc(100% - 3px))',
                }}
              >
                <span>Start Reproduction</span>
                <ArrowRight className="w-4 h-4 stroke-[3] text-[#FAF7F0]" />
              </button>
            </div>
          </div>
        )}

        {/* STEP 2: CONFIRM THE CLAIM (Field Desk Postcard Motif) */}
        {step === 2 && (
          <div className="space-y-6">
            {/* Collapse banner of selected source */}
            <div className="flex items-center justify-between bg-[#FAF7F0] px-5 py-3 rounded-lg border border-[#CDC5B4] text-xs font-mono text-[#1F2A44] shadow-sm">
              <div className="flex items-center gap-2">
                <span className="text-[#4A5470]">Source:</span>
                <span className="text-rust font-bold uppercase">
                  {sourceMode === 'custom' ? `Custom: ${repoUrl}` : `Benchmark: ${selectedCaseId}`}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-[#4A5470] hover:text-[#1F2A44] flex items-center gap-1.5 transition-colors border border-[#CDC5B4] px-2.5 py-1 rounded bg-[#E5DFD3]/40 hover:bg-[#E5DFD3]"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Change Source</span>
              </button>
            </div>

            {loadingClaims ? (
              <div className="bg-paper text-ink rounded-xl p-12 border border-kraft shadow-2xl text-center space-y-4">
                <div className="w-12 h-12 rounded-full border-4 border-rust border-t-transparent animate-spin mx-auto" />
                <h3 className="font-serif text-xl uppercase tracking-wider text-ink font-normal">
                  {progressState || 'Reading the paper PDF & inspecting the repository...'}
                </h3>
                <p className="text-xs text-ink-soft font-mono">
                  Extracting verbatim statements, reported metrics, tolerances, and parameter
                  defaults.
                </p>
              </div>
            ) : (
              /* Postcard Container */
              <div className="bg-paper text-ink rounded-xl border border-kraft shadow-2xl overflow-hidden relative">
                {/* Airmail stripe bar at top */}
                <div className="h-3 w-full bg-[repeating-linear-gradient(45deg,#B8572F,#B8572F_15px,#F1ECE0_15px,#F1ECE0_30px,#2F4F93_30px,#2F4F93_45px,#F1ECE0_45px,#F1ECE0_60px)]" />

                <div className="p-6 md:p-10 space-y-8">
                  {/* Postcard Header */}
                  <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-kraft/60 pb-6">
                    <div className="space-y-1">
                      <span className="text-[11px] font-mono tracking-widest uppercase text-rust font-bold">
                        PAR AVION · SCIENTIFIC CLAIM SPECIFICATION
                      </span>
                      <h2 className="font-serif text-2xl md:text-3xl uppercase tracking-wider text-ink-blue">
                        Paper Claims & Parameter Ledger
                      </h2>
                    </div>

                    {/* Postal Stamp Badge */}
                    <div className="postage-stamp bg-[#EBE5D6] border border-kraft p-2.5 rounded-sm text-center font-mono text-[10px] text-ink leading-tight select-none">
                      <div className="font-bold uppercase tracking-wider text-rust">INSPECTION</div>
                      <div>RERUN POST</div>
                      <div className="text-[9px] opacity-75">2026.10</div>
                    </div>
                  </div>

                  {/* REPO TRIAGE CARD */}
                  {triageReport && (
                    <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-5 space-y-4 shadow-sm font-mono text-xs">
                      <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-3">
                        <div className="flex items-center gap-2">
                          <Search className="w-4 h-4 text-rust" />
                          <span className="font-bold uppercase tracking-wider text-[#1F2A44]">
                            Repo Triage & Feasibility Check:
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-3 py-1 rounded text-[11px] font-bold uppercase tracking-wider ${
                              triageReport.verdict === 'FEASIBLE'
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                                : triageReport.verdict === 'FEASIBLE_WITH_PROVISIONING'
                                ? 'bg-blue-100 text-blue-800 border border-blue-300'
                                : triageReport.verdict === 'NEEDS_GPU'
                                ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                : 'bg-red-100 text-red-800 border border-red-300'
                            }`}
                          >
                            {triageReport.verdict}
                          </span>
                        </div>
                      </div>

                      <p className="text-xs text-[#4A5470] font-sans leading-relaxed">
                        {triageReport.reason}
                      </p>

                      {/* Signals Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
                        <div className="bg-[#FFFFFF] p-2.5 rounded border border-[#CDC5B4]">
                          <span className="text-[#4A5470] block">Frameworks:</span>
                          <span className="font-bold text-[#1F2A44]">
                            {triageReport.frameworks && triageReport.frameworks.length > 0
                              ? triageReport.frameworks.join(', ')
                              : 'Standard / CPU'}
                          </span>
                        </div>
                        <div className="bg-[#FFFFFF] p-2.5 rounded border border-[#CDC5B4]">
                          <span className="text-[#4A5470] block">Python Req:</span>
                          <span className="font-bold text-[#1F2A44]">
                            {triageReport.python_requires || 'Default (3.11)'}
                          </span>
                        </div>
                        <div className="bg-[#FFFFFF] p-2.5 rounded border border-[#CDC5B4]">
                          <span className="text-[#4A5470] block">GPU Guarding:</span>
                          <span className="font-bold text-[#1F2A44]">
                            {triageReport.gpu?.unguarded && triageReport.gpu.unguarded.length > 0
                              ? `${triageReport.gpu.unguarded.length} Unguarded (Blocker)`
                              : triageReport.gpu?.guarded && triageReport.gpu.guarded.length > 0
                              ? `${triageReport.gpu.guarded.length} Guarded (CPU Safe)`
                              : 'None (CPU Safe)'}
                          </span>
                        </div>
                        <div className="bg-[#FFFFFF] p-2.5 rounded border border-[#CDC5B4]">
                          <span className="text-[#4A5470] block">Code Stubs:</span>
                          <span className="font-bold text-[#1F2A44]">
                            {triageReport.stubs && triageReport.stubs.length > 0
                              ? `${triageReport.stubs.length} detected`
                              : '0 stubs (Clean)'}
                          </span>
                        </div>
                      </div>

                      {/* Evidence excerpts if any */}
                      {triageReport.evidence && triageReport.evidence.length > 0 && (
                        <div className="space-y-1.5 pt-2 border-t border-[#CDC5B4]">
                          <span className="text-[10px] text-rust font-bold uppercase tracking-wider block">
                            Triage Evidence Excerpts:
                          </span>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                            {triageReport.evidence.map((ev: string, idx: number) => (
                              <div
                                key={idx}
                                className="bg-[#FFFFFF] px-2.5 py-1.5 rounded text-[11px] font-mono border border-kraft/50 text-[#1F2A44]"
                              >
                                {ev}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Claims Table */}
                  <div className="space-y-3 font-mono text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold uppercase tracking-wider text-ink">
                        1. Extracted Paper Claims (Editable):
                      </span>
                      <button
                        type="button"
                        onClick={handleAddClaim}
                        className="px-3 py-1.5 rounded border border-kraft bg-[#FAF7F0] hover:bg-[#E5DFD3] text-[11px] font-bold uppercase tracking-wider text-ink transition-colors"
                      >
                        + Add a claim manually
                      </button>
                    </div>

                    <div className="overflow-x-auto bg-[#FFFFFF] rounded-lg border border-kraft shadow-sm">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-kraft text-ink-soft text-[11px] bg-[#FAF7F0]">
                            <th className="py-2.5 px-4">Claim ID</th>
                            <th className="py-2.5 px-4">Claim Statement</th>
                            <th className="py-2.5 px-4">Metric Key</th>
                            <th className="py-2.5 px-4">Reported Value</th>
                            <th className="py-2.5 px-4">Tolerance</th>
                            <th className="py-2.5 px-4">Provenance</th>
                            <th className="py-2.5 px-4"></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-kraft/50">
                          {claims.map((c, idx) => (
                            <tr key={c.id || idx} className="hover:bg-[#FAF7F0] transition-colors">
                              <td className="py-3 px-4 font-bold text-rust">
                                {c.id || `C-${idx + 1}`}
                              </td>
                              <td className="py-3 px-4 max-w-xs font-serif italic text-xs text-ink-blue">
                                <input
                                  type="text"
                                  value={c.statement}
                                  onChange={(e) => {
                                    const updated = [...claims];
                                    updated[idx].statement = e.target.value;
                                    setClaims(updated);
                                  }}
                                  className="w-full bg-[#F4F1E8] border border-kraft rounded px-2 py-1 text-xs text-ink focus:outline-none focus:border-rust"
                                />
                              </td>
                              <td className="py-3 px-4 font-mono text-xs text-ink-soft">
                                <input
                                  type="text"
                                  value={c.result_key || c.metric || ''}
                                  placeholder="e.g. test_loss"
                                  onChange={(e) => {
                                    const updated = [...claims];
                                    updated[idx] = {
                                      ...updated[idx],
                                      result_key: e.target.value,
                                      metric: e.target.value,
                                    };
                                    setClaims(updated);
                                  }}
                                  className="w-36 bg-[#F4F1E8] border border-kraft rounded px-2 py-1 text-xs text-ink focus:outline-none focus:border-rust"
                                />
                              </td>
                              <td className="py-3 px-4">
                                <input
                                  type="number"
                                  step="0.001"
                                  value={c.reported}
                                  onChange={(e) => {
                                    const updated = [...claims];
                                    updated[idx].reported = parseFloat(e.target.value);
                                    setClaims(updated);
                                  }}
                                  className="w-24 bg-[#F4F1E8] border border-kraft rounded px-2 py-1 font-mono text-xs font-bold text-ink focus:outline-none focus:border-rust"
                                />
                              </td>
                              <td className="py-3 px-4">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-mono text-xs text-ink">±</span>
                                  <input
                                    type="number"
                                    step="0.001"
                                    value={c.tolerance?.value ?? 0.01}
                                    onChange={(e) => {
                                      const updated = [...claims];
                                      updated[idx] = {
                                        ...updated[idx],
                                        tolerance: {
                                          type: updated[idx].tolerance?.type ?? 'abs',
                                          value: parseFloat(e.target.value),
                                        },
                                      };
                                      setClaims(updated);
                                    }}
                                    className="w-20 bg-[#F4F1E8] border border-kraft rounded px-2 py-1 font-mono text-xs text-ink focus:outline-none focus:border-rust"
                                  />
                                  <span className="text-[10px] text-ink-soft">
                                    {c.tolerance?.type ?? 'abs'}
                                  </span>
                                </div>
                              </td>
                              <td className="py-3 px-4">
                                {c.quote_verified === false ? (
                                  <span
                                    className="text-[10px] font-bold uppercase tracking-wider text-amber-800"
                                    title="Supplied by the operator; not verified against the paper text"
                                  >
                                    operator
                                  </span>
                                ) : (
                                  <span
                                    className="text-[10px] font-bold uppercase tracking-wider text-emerald-700"
                                    title="Quote found verbatim in the paper"
                                  >
                                    verified
                                  </span>
                                )}
                              </td>
                              <td className="py-3 px-4">
                                <button
                                  type="button"
                                  onClick={() => handleRemoveClaim(idx)}
                                  className="text-[11px] text-fail hover:underline"
                                >
                                  remove
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Paper Settings (Read-only verbatim citations) */}
                  {paperSettings.length > 0 && (
                    <div className="space-y-3 font-mono text-xs">
                      <span className="font-bold uppercase tracking-wider text-ink block">
                        2. Verbatim Paper Settings (Grounded Citations):
                      </span>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {paperSettings.map((ps, idx) => (
                          <div
                            key={idx}
                            className="bg-[#FFFFFF] p-3.5 rounded-lg border border-kraft space-y-1.5 shadow-sm"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-ink">{ps.key}</span>
                              <span className="px-2 py-0.5 rounded bg-[#FAF7F0] border border-kraft/50 text-rust font-bold">
                                {String(ps.value)}
                              </span>
                            </div>
                            <div className="text-[11px] text-ink-blue italic font-serif">
                              "{ps.source_quote}"
                            </div>
                            <div className="text-[10px] text-ink-soft font-semibold">
                              Citation: {ps.source_ref}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Run Command Field */}
                  <div className="space-y-2 font-mono text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold uppercase tracking-wider text-ink">
                        3. Planned Run Command (Editable):
                      </span>
                      <button
                        type="button"
                        onClick={handleCopyCommand}
                        className="flex items-center gap-1 text-[11px] text-ink-soft hover:text-ink"
                      >
                        {copiedCmd ? (
                          <Check className="w-3.5 h-3.5 text-ok" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        <span>Copy command</span>
                      </button>
                    </div>

                    <input
                      type="text"
                      value={runCommand}
                      onChange={(e) => setRunCommand(e.target.value)}
                      className="w-full bg-[#FAF7F0] text-[#1F2A44] font-mono text-xs rounded-lg px-4 py-3 border border-[#CDC5B4] focus:outline-none focus:border-rust shadow-inner font-semibold"
                    />
                  </div>

                  {/* Command candidates discovered in the repository */}
                  {commandCandidates.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[11px] text-[#4A5470] uppercase tracking-wider font-semibold">
                        Commands found in this repository (click to use):
                      </span>
                      <div className="flex flex-wrap gap-2">
                        {commandCandidates.map((cmd) => (
                          <button
                            key={cmd}
                            type="button"
                            onClick={() => setRunCommand(cmd)}
                            className={`px-2.5 py-1.5 rounded border font-mono text-[11px] transition-colors ${
                              runCommand === cmd
                                ? 'bg-amber-100 border-amber-400 text-amber-900 font-bold'
                                : 'bg-[#FAF7F0] border-[#CDC5B4] text-[#1F2A44] hover:bg-[#E5DFD3]'
                            }`}
                          >
                            {cmd}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* No claim could be verified against the paper */}
                  {claims.length === 0 && (
                    <div className="p-4 rounded-lg bg-amber-50 border-2 border-amber-300 text-amber-900 font-mono text-xs space-y-1.5">
                      <div className="font-bold uppercase tracking-wider">
                        No claim could be verified against the paper
                      </div>
                      {extractionIssues.length > 0 ? (
                        <ul className="list-disc list-inside space-y-0.5">
                          {extractionIssues.map((issue, i) => (
                            <li key={i}>{issue}</li>
                          ))}
                        </ul>
                      ) : (
                        <p>Claim extraction returned nothing for this paper.</p>
                      )}
                      <p className="text-[11px]">
                        A claim is only accepted when its quote appears verbatim in the paper text,
                        which is what stops an invented number being treated as verified. Nothing
                        has been substituted here. Use <strong>“+ Add a claim manually”</strong> in
                        the claims table below to enter the metric and the value the paper reports,
                        or stop at triage. A claim you add is recorded as operator-supplied, not as
                        verified from the paper.
                      </p>
                    </div>
                  )}

                  {/* Confirm error from the server */}
                  {confirmError && (
                    <div className="p-4 rounded-lg bg-red-50 border-2 border-red-300 text-red-900 font-mono text-xs">
                      <span className="font-bold uppercase tracking-wider block mb-1">
                        Launch rejected
                      </span>
                      {confirmError}
                    </div>
                  )}

                  {/* Triage block notice */}
                  {isTriageBlocked && (
                    <div className="p-4 rounded-lg bg-red-50 border-2 border-red-300 text-red-900 font-mono text-xs space-y-1.5">
                      <div className="font-bold uppercase tracking-wider">
                        Execution blocked: {triageReport?.verdict}
                      </div>
                      <p className="leading-relaxed">{triageBlockReason}</p>
                      <p className="text-[11px] text-red-800">
                        This repository cannot be executed in the sandbox, so launching would only
                        produce an UNABLE_TO_EXECUTE verdict. Use “Triage Only” to keep the
                        feasibility report.
                      </p>
                    </div>
                  )}

                  {/* Actions Bar */}
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-kraft/60">
                    <button
                      type="button"
                      onClick={() => setShowRejectConfirm(true)}
                      className="text-xs font-mono text-fail hover:underline"
                    >
                      Reject extracted claims & abort
                    </button>

                    <div className="flex items-center gap-3 w-full sm:w-auto">
                      <button
                        type="button"
                        onClick={() => {
                          if (projectId) navigate(`/p/${projectId}`);
                        }}
                        className="w-full sm:w-auto px-4 py-3 rounded border border-[#CDC5B4] bg-[#FAF7F0] text-xs font-mono font-bold text-[#1F2A44] hover:bg-[#E5DFD3] transition-colors shadow-sm"
                      >
                        Triage Only (Stop Here)
                      </button>

                      <button
                        type="button"
                        onClick={handleConfirmClaims}
                        disabled={submittingConfirm || isTriageBlocked}
                        title={
                          isTriageBlocked
                            ? `Blocked by triage: ${triageReport?.verdict}. ${triageBlockReason}`
                            : undefined
                        }
                        className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-[0.2em] border border-l-4 border-l-[#7A3317] shadow-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-rust"
                        style={{
                          clipPath:
                            'polygon(0% 2px, 2px 0%, calc(100% - 2px) 0%, 100% 2px, 100% calc(100% - 2px), calc(100% - 2px) 100%, 2px 100%, 0% calc(100% - 2px))',
                        }}
                      >
                        <Send className="w-4 h-4 text-[#FAF7F0]" />
                        <span>
                          {isTriageBlocked
                            ? 'Launch Blocked by Triage'
                            : submittingConfirm
                            ? 'Confirming...'
                            : 'Confirm Claims & Launch Run →'}
                        </span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Reject Confirmation Modal */}
        {showRejectConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
            <div className="bg-[#FAF7F0] border border-[#CDC5B4] rounded-xl p-6 max-w-sm w-full space-y-4 shadow-2xl text-[#1F2A44] font-mono text-xs">
              <h3 className="text-base font-serif uppercase tracking-wide text-[#1F2A44] font-bold">
                Reject All Claims?
              </h3>
              <p className="text-xs text-[#4A5470] leading-relaxed font-sans">
                Rejecting claims will mark the reproduction run as INCONCLUSIVE with reason "no
                claim confirmed".
              </p>
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  onClick={() => setShowRejectConfirm(false)}
                  className="px-3.5 py-1.5 rounded border border-[#CDC5B4] text-xs text-[#4A5470] hover:bg-[#E5DFD3] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleRejectClaims}
                  className="px-3.5 py-1.5 rounded bg-fail text-white font-bold text-xs uppercase tracking-wider shadow-sm"
                >
                  Confirm Reject
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default NewProject;

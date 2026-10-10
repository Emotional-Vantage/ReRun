import type {
  BenchmarkCase,
  Claim,
  CriticReview,
  EvidenceItem,
  HealthResponse,
  Patch,
  ProjectStateSummary,
  ReportData,
} from './types';

const BASE_URL = '';

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${BASE_URL}/api/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return res.json();
}

export async function fetchBenchmarks(): Promise<BenchmarkCase[]> {
  const res = await fetch(`${BASE_URL}/api/benchmarks`);
  if (!res.ok) throw new Error(`Failed to fetch benchmarks: ${res.statusText}`);
  return res.json();
}

export async function createProject(benchmarkId: string, allowHighRisk: boolean = false): Promise<{ project_id: string }> {
  const res = await fetch(`${BASE_URL}/api/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ benchmark_id: benchmarkId, allow_high_risk: allowHighRisk }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to create project: ${res.statusText}`);
  }
  return res.json();
}

export async function createCustomProject(
  repoUrl: string,
  paperFile: File,
  repoRef?: string,
  allowHighRisk: boolean = false
): Promise<{ project_id: string }> {
  const formData = new FormData();
  formData.append('repo_url', repoUrl);
  formData.append('paper', paperFile);
  if (repoRef) {
    formData.append('repo_ref', repoRef);
  }
  formData.append('allow_high_risk', String(allowHighRisk));

  const res = await fetch(`${BASE_URL}/api/projects`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to create project: ${res.statusText}`);
  }
  return res.json();
}

export async function startProject(projectId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/start`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to start project: ${res.statusText}`);
}

export async function fetchProjectState(projectId: string): Promise<ProjectStateSummary> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}`);
  if (!res.ok) throw new Error(`Failed to fetch project state: ${res.statusText}`);
  return res.json();
}

export async function fetchTriageReport(projectId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/triage`, {
    method: 'POST',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || `Failed to fetch triage report: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchClaimsDraft(projectId: string): Promise<{
  claims: Claim[];
  paper_settings: any[];
  command: string | null;
  command_candidates: string[];
  extraction_issues: string[];
}> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/claims-draft`);
  if (!res.ok) throw new Error(`Failed to fetch claims draft: ${res.statusText}`);
  return res.json();
}

export async function confirmClaims(
  projectId: string,
  claims: Claim[],
  command: string,
  allowHighRisk: boolean = false
): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/claims/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ claims, command, allow_high_risk: allowHighRisk }),
  });
  if (!res.ok) throw new Error(`Failed to confirm claims: ${res.statusText}`);
}

export async function rejectClaims(projectId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/claims/reject`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to reject claims: ${res.statusText}`);
}

export async function fetchPendingApproval(projectId: string): Promise<{
  approval_id: string;
  project_id: string;
  patch: Patch;
  reviews: CriticReview[];
  critic_review: CriticReview | null;
  banner: string | null;
  requires_extra_confirm: boolean;
}> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/approvals/pending`);
  if (!res.ok) throw new Error(`Failed to fetch pending approval: ${res.statusText}`);
  return res.json();
}

export async function submitApproval(
  projectId: string,
  approvalId: string,
  decision: 'approve' | 'reject' | 'edit',
  confirmExtra: boolean = false,
  comment: string = '',
  edits?: any[]
): Promise<any> {
  // Project-scoped: approval ids are only unique within a project, so posting to the
  // unscoped /api/approvals/{id} could apply the decision to a different project.
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/approvals/${approvalId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, confirm_extra: confirmExtra, comment, edits, project_id: projectId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to submit approval: ${res.statusText}`);
  }
  return res.json();
}

/** The server-rendered Markdown report — the complete document, not a client-side summary. */
export async function fetchReportMarkdown(projectId: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/report.md`);
  if (!res.ok) throw new Error(`Failed to fetch report markdown: ${res.statusText}`);
  return res.text();
}

/** The project's evidence ledger. Entries the stores cannot serve carry available:false. */
export async function fetchEvidenceLedger(projectId: string): Promise<EvidenceItem[]> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/evidence`);
  if (!res.ok) throw new Error(`Failed to fetch evidence ledger: ${res.statusText}`);
  return res.json();
}

/** Emergency stop: terminates every running project and kills all sandbox containers. */
export async function killSwitch(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/api/admin/kill-switch`, { method: 'POST' });
  if (!res.ok) throw new Error(`Kill switch failed: ${res.statusText}`);
  return res.json();
}

export async function fetchEvidence(projectId: string, evidenceId: string): Promise<EvidenceItem> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/evidence/${evidenceId}`);
  if (!res.ok) throw new Error(`Failed to fetch evidence: ${res.statusText}`);
  return res.json();
}

export async function fetchRunLog(projectId: string, runN: number): Promise<string> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/logs/${runN}`);
  if (!res.ok) throw new Error(`Failed to fetch run log: ${res.statusText}`);
  const data = await res.json();
  return data.log || '';
}

export async function fetchReport(projectId: string): Promise<ReportData> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/report`);
  if (!res.ok) throw new Error(`Failed to fetch report: ${res.statusText}`);
  return res.json();
}

export async function abortProject(projectId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/abort`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to abort project: ${res.statusText}`);
}

export async function approveProvisioning(projectId: string, packages?: string[]): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/provisioning/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ packages, confirm: true }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to approve provisioning: ${res.statusText}`);
  }
  return res.json();
}

export async function rejectProvisioning(projectId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/provisioning/reject`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to reject provisioning: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchProvisioningPlan(projectId: string): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/projects/${projectId}/provisioning/plan`);
  if (!res.ok) throw new Error(`Failed to fetch provisioning plan: ${res.statusText}`);
  return res.json();
}

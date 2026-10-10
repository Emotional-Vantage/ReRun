import React, { useState } from 'react';
import { AlertTriangle, Check, X, PackageSearch } from 'lucide-react';

export interface ProvisioningPackage {
  name: string;
  raw_spec?: string;
  version_constraint?: string;
  source_file?: string;
  has_wheel?: boolean;
  sdist_only?: boolean;
  size_bytes?: number;
  reason?: string;
}

interface ProvisioningModalProps {
  isOpen: boolean;
  packages: string[];
  details?: ProvisioningPackage[];
  pythonImage?: string;
  warnings?: string[];
  onApprove: () => Promise<void> | void;
  onReject: () => Promise<void> | void;
}

const formatSize = (bytes?: number) => {
  if (!bytes || bytes <= 0) return '—';
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / 1024).toFixed(0)} KB`;
};

export const ProvisioningModal: React.FC<ProvisioningModalProps> = ({
  isOpen,
  packages,
  details,
  pythonImage,
  warnings,
  onApprove,
  onReject,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const rows: ProvisioningPackage[] =
    details && details.length > 0 ? details : packages.map((name) => ({ name }));

  const totalBytes = rows.reduce((sum, p) => sum + (p.size_bytes || 0), 0);

  const run = async (action: () => Promise<void> | void, label: string) => {
    if (isSubmitting) return;
    setError(null);
    setIsSubmitting(true);
    try {
      await action();
    } catch (e: any) {
      setError(e?.message || `${label} failed.`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4 overflow-y-auto animate-fade-in">
      <div className="w-full max-w-3xl bg-[#FAF7F0] border-2 border-rust rounded-xl p-6 shadow-2xl space-y-5 max-h-[90vh] overflow-y-auto font-mono text-xs text-[#1F2A44]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#CDC5B4] pb-4">
          <div className="flex items-center gap-2.5">
            <span className="w-8 h-8 rounded bg-amber-100 border border-amber-300 flex items-center justify-center text-amber-800">
              <PackageSearch className="w-4 h-4" />
            </span>
            <div>
              <h2 className="text-base font-serif uppercase tracking-wide font-bold">
                Human Approval Gate: Dependency Provisioning
              </h2>
              <span className="text-[11px] text-[#4A5470]">
                {rows.length} package{rows.length === 1 ? '' : 's'} will be downloaded into this
                project's offline wheelhouse
              </span>
            </div>
          </div>
          {pythonImage && (
            <span className="px-2.5 py-1 rounded bg-[#E5DFD3] border border-[#CDC5B4] text-[10px] font-bold uppercase tracking-wider">
              {pythonImage}
            </span>
          )}
        </div>

        {/* What this does */}
        <div className="p-3.5 rounded-lg bg-[#F4F1E8] border border-[#CDC5B4] leading-relaxed">
          Wheels are fetched in an isolated container that mounts only the destination
          wheelhouse, never the repository. The experiment itself still runs offline. Nothing
          is installed until you approve.
        </div>

        {/* Warnings */}
        {warnings && warnings.length > 0 && (
          <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-300 text-amber-900 space-y-1.5">
            <div className="flex items-center gap-2 font-bold">
              <AlertTriangle className="w-4 h-4 text-amber-700" />
              <span>Review before approving</span>
            </div>
            <ul className="list-disc list-inside space-y-1 text-[11px] leading-relaxed">
              {warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Package table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#CDC5B4] text-[#4A5470] text-[10px] uppercase tracking-wider">
                <th className="py-2 px-2">Package</th>
                <th className="py-2 px-2">Version</th>
                <th className="py-2 px-2">Declared in</th>
                <th className="py-2 px-2">Wheel</th>
                <th className="py-2 px-2">Size</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#CDC5B4]/50">
              {rows.map((p) => (
                <tr key={p.name}>
                  <td className="py-2 px-2 font-bold">{p.name}</td>
                  <td className="py-2 px-2">
                    {p.version_constraint ? (
                      p.version_constraint
                    ) : (
                      <span className="text-amber-800">unpinned</span>
                    )}
                  </td>
                  <td className="py-2 px-2 text-[#4A5470]">{p.source_file || '—'}</td>
                  <td className="py-2 px-2">
                    {p.sdist_only ? (
                      <span className="text-red-700 font-bold">source only</span>
                    ) : (
                      <span className="text-emerald-700">binary</span>
                    )}
                  </td>
                  <td className="py-2 px-2">{formatSize(p.size_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalBytes > 0 && (
          <p className="text-[11px] text-[#4A5470]">
            Estimated download: {formatSize(totalBytes)}. Large packages such as torch can take
            several minutes; the dialog stays open until the download finishes.
          </p>
        )}

        {error && (
          <div className="p-3 rounded bg-red-50 border border-red-300 text-red-800 text-[11px]">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#CDC5B4]">
          <button
            type="button"
            onClick={() => run(onReject, 'Reject')}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-sm bg-red-50 hover:bg-red-100 text-red-700 border border-red-300 font-bold text-xs uppercase tracking-wider transition-colors disabled:opacity-50"
          >
            <X className="w-4 h-4" />
            <span>Reject &amp; Stop</span>
          </button>
          <button
            type="button"
            onClick={() => run(onApprove, 'Approve')}
            disabled={isSubmitting}
            className="flex items-center gap-1.5 px-5 py-2.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-[#7A3317] shadow-md active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Check className="w-4 h-4 stroke-[3]" />
            <span>{isSubmitting ? 'Downloading wheels…' : 'Approve & Provision'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};

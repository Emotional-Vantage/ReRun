import React, { useEffect, useState } from 'react';
import { FileCheck, ArrowRight, X } from 'lucide-react';

interface ReportToastProps {
  /** Verdict to name in the toast, e.g. REPRODUCED. */
  status?: string;
  /** Seconds the toast stays up before retiring itself. */
  dwellSeconds?: number;
  onOpen: () => void;
  onDismiss: () => void;
}

/*
  The report banner lives at the top of the dashboard, so a run that finishes
  while the operator is reading the trace or the container log finishes
  silently -- the only signal is above the fold. This is that signal: it
  appears wherever they are, says the verdict, and gets out of the way on its
  own.

  It is a torn slip of paper rather than a rectangular notification, to sit
  with the rest of the page, and it is a `status` region rather than an
  `alert`, since a finished run is good news and not an interruption.
*/
export const ReportToast: React.FC<ReportToastProps> = ({
  status,
  dwellSeconds = 9,
  onOpen,
  onDismiss,
}) => {
  const [leaving, setLeaving] = useState(false);

  const retire = () => {
    setLeaving(true);
    // Let the exit transition play out before the node is unmounted.
    window.setTimeout(onDismiss, 260);
  };

  useEffect(() => {
    const t = window.setTimeout(retire, dwellSeconds * 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dwellSeconds]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-6 right-6 z-50 w-[330px] transition-all duration-250 ease-out ${
        leaving ? 'opacity-0 translate-y-2' : 'opacity-100 translate-y-0'
      }`}
      style={{ transform: leaving ? undefined : 'rotate(-0.7deg)' }}
    >
      <div className="relative bg-paper border border-kraft border-l-4 border-l-rust rounded-sm shadow-[0_14px_34px_-10px_rgba(31,42,68,0.45)]">
        {/* A strip of washi tape, as on the polaroids elsewhere in the product. */}
        <div
          className="absolute -top-2.5 left-7 w-16 h-5 washi-tape rotate-2"
          aria-hidden="true"
        />

        <button
          type="button"
          onClick={retire}
          aria-label="Dismiss"
          className="absolute top-2 right-2 p-1 text-ink-soft hover:text-ink rounded-sm focus:outline-none focus-visible:ring-1 focus-visible:ring-rust"
        >
          <X className="w-3.5 h-3.5" />
        </button>

        <div className="p-4 pt-5">
          <div className="flex items-start gap-2.5">
            <FileCheck className="w-4 h-4 text-rust shrink-0 mt-0.5" />
            <div className="min-w-0">
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-rust-ink font-bold">
                The report is ready
              </p>
              <p className="font-serif text-base text-ink leading-snug mt-1">
                {status ? (
                  <>
                    The run finished. Verdict:{' '}
                    <span className="text-rust-ink font-semibold">{status}</span>.
                  </>
                ) : (
                  <>The run finished and the report has been written.</>
                )}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpen}
            className="mt-3.5 w-full flex items-center justify-center gap-2 px-4 py-2 rounded-sm bg-rust hover:bg-[#A34B26] text-paper font-mono font-bold text-[11px] uppercase tracking-wider border-l-4 border-l-[#7A3317] active:scale-[0.98] transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-rust-ink"
          >
            <span>Read the report</span>
            <ArrowRight className="w-3.5 h-3.5 stroke-[3]" />
          </button>
        </div>
      </div>
    </div>
  );
};

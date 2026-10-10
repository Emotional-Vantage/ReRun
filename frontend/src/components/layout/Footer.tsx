import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="w-full bg-[#DFD8CA] border-t border-[#CDC5B4] text-[#4A5470] py-12 px-4 sm:px-6 font-mono text-xs">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2.5">
              <svg
                viewBox="0 0 24 24"
                className="w-5 h-5 stroke-rust fill-none"
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
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-sm bg-[#FAF7F0] text-[#1F2A44] border border-[#CDC5B4] shadow-sm font-bold">
                RESEARCH EDITION
              </span>
            </div>
            <p className="text-xs text-[#4A5470] max-w-md font-sans leading-relaxed">
              Autonomous AI verification agent for computational research reproducibility. Locked sandbox, deterministic policy, and human sign-off.
            </p>
          </div>

          <div className="flex flex-wrap gap-6 text-xs uppercase tracking-wider text-[#4A5470] font-semibold">
            <a href="/#how-it-works" className="hover:text-rust transition-colors">How it works</a>
            <a href="/#roles" className="hover:text-rust transition-colors">Roles</a>
            <a href="/#trust" className="hover:text-rust transition-colors">Trust</a>
            <a href="/#demo" className="hover:text-rust transition-colors">Demo</a>
            <a href="/#faq" className="hover:text-rust transition-colors">FAQ</a>
          </div>
        </div>

        {/* Evaluation Scope & Integrity */}
        <div className="pt-6 border-t border-[#CDC5B4] flex flex-col md:flex-row items-center justify-between gap-4 text-[11px] font-mono text-[#4A5470]/90">
          <p className="italic text-center md:text-left">
            "Benchmarks are synthetic. Rerun checks computational reproducibility only; a failed reproduction does not mean a paper is wrong."
          </p>
          <div className="flex items-center gap-4 font-semibold text-[#1F2A44]">
            <span>Rerun Lab · 2026</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

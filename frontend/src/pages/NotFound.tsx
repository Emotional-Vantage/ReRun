import React from 'react';
import { Link } from 'react-router-dom';
import { Compass, ArrowLeft } from 'lucide-react';

export const NotFound: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#EDE7DB] text-[#1F2A44] flex flex-col items-center justify-center p-6 text-center font-mono">
      <div className="w-16 h-16 rounded-2xl bg-[#FAF7F0] border border-[#CDC5B4] flex items-center justify-center text-rust mb-6 shadow-sm">
        <Compass className="w-8 h-8" />
      </div>
      <h1 className="font-serif text-3xl font-normal uppercase tracking-wide text-[#1F2A44] mb-2">
        404 — Page Not Found
      </h1>
      <p className="text-xs text-[#4A5470] max-w-sm mb-6 leading-relaxed">
        The requested case file or route does not exist in the field desk ledger.
      </p>
      <Link
        to="/"
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-sm bg-rust hover:bg-[#A34B26] text-[#FAF7F0] font-bold text-xs uppercase tracking-wider border border-l-4 border-l-[#7A3317] transition-all shadow-sm"
      >
        <ArrowLeft className="w-4 h-4 text-[#FAF7F0]" />
        <span>Return to Field Notebook</span>
      </Link>
    </div>
  );
};

export default NotFound;

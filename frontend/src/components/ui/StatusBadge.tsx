import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle, Ban, HelpCircle } from 'lucide-react';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showIcon?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
  className = '',
  showIcon = true,
}) => {
  const normStatus = (status || 'UNKNOWN').toUpperCase();

  const config = {
    REPRODUCED: {
      label: 'REPRODUCED',
      bg: 'bg-emerald-100 text-emerald-800 border-emerald-400 font-bold',
      icon: CheckCircle2,
    },
    PARTIALLY_REPRODUCED: {
      label: 'PARTIALLY REPRODUCED',
      bg: 'bg-amber-100 text-amber-900 border-amber-400 font-bold',
      icon: AlertTriangle,
    },
    NOT_REPRODUCED: {
      label: 'NOT REPRODUCED',
      bg: 'bg-red-100 text-red-800 border-red-400 font-bold',
      icon: XCircle,
    },
    UNABLE_TO_EXECUTE: {
      label: 'UNABLE TO EXECUTE',
      bg: 'bg-[#E5DFD3] text-[#4A5470] border-[#CDC5B4] font-bold',
      icon: Ban,
    },
    INCONCLUSIVE: {
      label: 'INCONCLUSIVE',
      bg: 'bg-purple-100 text-purple-800 border-purple-400 font-bold',
      icon: HelpCircle,
    },
  }[normStatus] || {
    label: normStatus,
    bg: 'bg-[#FAF7F0] text-[#1F2A44] border-[#CDC5B4]',
    icon: HelpCircle,
  };

  const Icon = config.icon;

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 gap-1',
    md: 'text-xs md:text-sm px-3 py-1 gap-1.5',
    lg: 'text-sm md:text-base px-4 py-1.5 gap-2 font-semibold',
  }[size];

  return (
    <span
      className={`inline-flex items-center font-mono tracking-wide border rounded-full ${config.bg} ${sizeClasses} ${className}`}
    >
      {showIcon && <Icon className={size === 'lg' ? 'w-5 h-5' : size === 'sm' ? 'w-3 h-3' : 'w-4 h-4'} />}
      <span>{config.label}</span>
    </span>
  );
};

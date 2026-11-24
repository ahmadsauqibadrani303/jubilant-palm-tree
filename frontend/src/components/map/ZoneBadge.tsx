import React from 'react';
import type { ZoneInfo } from '../../types/api.types';

interface ZoneBadgeProps {
  zone?: ZoneInfo | null;
  zoneKey?: string;
  zoneLabel?: string;
  isOverridden?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const ZoneBadge: React.FC<ZoneBadgeProps> = ({
  zone,
  zoneKey,
  zoneLabel,
  isOverridden,
  size = 'md',
}) => {
  const effectiveKey = zone?.zone_key || zoneKey || 'unknown';
  const effectiveLabel = zone?.zone_label || zoneLabel || (
    effectiveKey === 'high' ? 'Zona Subur Tinggi' :
    effectiveKey === 'medium' ? 'Zona Subur Sedang' :
    effectiveKey === 'low' ? 'Zona Subur Rendah' : 'Data Belum Lengkap'
  );
  const overridden = zone?.is_overridden ?? isOverridden ?? false;

  let colorClasses = 'bg-slate-100 text-slate-700 border-slate-300';
  let dotColor = 'bg-slate-400';

  if (effectiveKey === 'high') {
    colorClasses = 'bg-emerald-50 text-emerald-800 border-emerald-300';
    dotColor = 'bg-emerald-500';
  } else if (effectiveKey === 'medium') {
    colorClasses = 'bg-amber-50 text-amber-800 border-amber-300';
    dotColor = 'bg-amber-500';
  } else if (effectiveKey === 'low') {
    colorClasses = 'bg-rose-50 text-rose-800 border-rose-300';
    dotColor = 'bg-rose-500';
  }

  const sizeClasses =
    size === 'sm'
      ? 'text-xs px-2 py-0.5'
      : size === 'lg'
      ? 'text-sm px-3.5 py-1.5'
      : 'text-xs px-2.5 py-1';

  return (
    <div className="inline-flex items-center gap-1.5 flex-wrap">
      <span
        className={`inline-flex items-center gap-1.5 font-medium rounded-full border ${sizeClasses} ${colorClasses}`}
      >
        <span className={`w-2 h-2 rounded-full ${dotColor}`} />
        <span>{effectiveLabel}</span>
      </span>
      {overridden && (
        <span
          title="Label zona disesuaikan secara manual oleh pakar agronomi"
          className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200"
        >
          Koreksi Pakar
        </span>
      )}
    </div>
  );
};

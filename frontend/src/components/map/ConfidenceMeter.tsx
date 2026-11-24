import React, { useState } from 'react';
import { ChevronDownIcon, ChevronUpIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import type { ConfidenceInfo } from '../../types/api.types';

interface ConfidenceMeterProps {
  confidence?: ConfidenceInfo | null;
}

export const ConfidenceMeter: React.FC<ConfidenceMeterProps> = ({ confidence }) => {
  const [showDetails, setShowDetails] = useState(false);

  if (!confidence) {
    return (
      <div className="text-xs text-on-surface-variant flex items-center gap-1">
        <InformationCircleIcon className="w-4 h-4" />
        <span>Skor keyakinan tidak tersedia</span>
      </div>
    );
  }

  const { score, category, breakdown } = confidence;
  const scorePercent = Math.round(score * 100);

  // Styling berdasarkan kategori ('tinggi' | 'sedang' | 'rendah')
  let barColor = 'bg-rose-500';
  let badgeColor = 'bg-rose-50 text-rose-700 border-rose-200';
  let categoryLabel = 'Keyakinan Rendah';

  if (category === 'tinggi') {
    barColor = 'bg-emerald-500';
    badgeColor = 'bg-emerald-50 text-emerald-700 border-emerald-200';
    categoryLabel = 'Keyakinan Tinggi';
  } else if (category === 'sedang') {
    barColor = 'bg-amber-500';
    badgeColor = 'bg-amber-50 text-amber-700 border-amber-200';
    categoryLabel = 'Keyakinan Sedang';
  }

  return (
    <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-xl p-3 space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-on-surface flex items-center gap-1.5">
          Tingkat Keyakinan AI
        </span>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full border text-[11px] font-semibold ${badgeColor}`}>
            {categoryLabel}
          </span>
          <span className="font-bold text-on-surface">{scorePercent}%</span>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-surface-container-high rounded-full h-2 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${Math.min(100, Math.max(5, scorePercent))}%` }}
        />
      </div>

      {/* Toggle Details */}
      <div className="pt-1">
        <button
          type="button"
          onClick={() => setShowDetails(!showDetails)}
          className="text-[11px] text-primary hover:text-primary-dark font-medium flex items-center gap-1 transition-colors"
        >
          <span>{showDetails ? 'Sembunyikan rincian bobot' : 'Lihat rincian kalkulasi keyakinan'}</span>
          {showDetails ? <ChevronUpIcon className="w-3 h-3" /> : <ChevronDownIcon className="w-3 h-3" />}
        </button>

        {showDetails && breakdown && (
          <div className="mt-2 pt-2 border-t border-outline-variant/40 space-y-1.5 text-[11px] text-on-surface-variant">
            <div className="flex justify-between items-center">
              <span>Margin Klaster Model (Bobot 35%):</span>
              <span className="font-semibold text-on-surface">
                {Math.round(breakdown.cluster_margin * 100)}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span>Kelengkapan Parameter Hara (Bobot 35%):</span>
              <span className="font-semibold text-on-surface">
                {Math.round(breakdown.data_completeness * 100)}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span>Keselarasan Aturan & Zona (Bobot 30%):</span>
              <span className="font-semibold text-on-surface">
                {Math.round(breakdown.rule_zone_agreement * 100)}%
              </span>
            </div>
            {breakdown.boundary_proximity_penalty > 0 && (
              <div className="flex justify-between items-center text-rose-600 font-medium">
                <span>Pinalti Dekat Batas Ambang Hara:</span>
                <span>-{Math.round(breakdown.boundary_proximity_penalty * 100)}%</span>
              </div>
            )}
            <p className="text-[10px] text-on-surface-variant/80 italic pt-1">
              *Skor dihitung secara objektif dari data terukur dan ketegasan batas klasifikasi.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

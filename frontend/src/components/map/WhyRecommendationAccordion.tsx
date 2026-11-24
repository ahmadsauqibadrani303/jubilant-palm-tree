import React, { useState } from 'react';
import { 
  ChevronDownIcon, 
  ChevronUpIcon, 
  LightBulbIcon, 
  ExclamationCircleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import type { LimitingFactorDetail, CropRankingItem } from '../../types/api.types';

interface WhyRecommendationAccordionProps {
  topCrop?: CropRankingItem;
  limitingFactors: LimitingFactorDetail[];
  summary: string;
}

export const WhyRecommendationAccordion: React.FC<WhyRecommendationAccordionProps> = ({
  topCrop,
  limitingFactors,
  summary,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="border border-outline-variant/60 rounded-xl overflow-hidden bg-surface-container-lowest">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between text-left hover:bg-surface-container-low transition-colors"
      >
        <div className="flex items-center gap-2">
          <LightBulbIcon className="w-4 h-4 text-primary" />
          <span className="text-xs font-semibold text-on-surface">
            Kenapa Rekomendasi Ini? (Rasional Agronomi)
          </span>
        </div>
        {isOpen ? (
          <ChevronUpIcon className="w-4 h-4 text-on-surface-variant" />
        ) : (
          <ChevronDownIcon className="w-4 h-4 text-on-surface-variant" />
        )}
      </button>

      {isOpen && (
        <div className="px-3.5 pb-3 pt-1 border-t border-outline-variant/40 space-y-3 text-xs text-on-surface-variant">
          {/* Ringkasan Singkat */}
          <p className="text-on-surface leading-relaxed">{summary}</p>

          {/* Basis Ilmiah Liebig */}
          <div className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/40 space-y-1">
            <span className="font-semibold text-on-surface text-[11px] block">
              Prinsip Evaluasi (Hukum Minimum Liebig):
            </span>
            <p className="text-[11px] leading-relaxed">
              Potensi pertumbuhan tanaman dibatasi oleh unsur hara yang berada dalam kondisi paling minimal, bukan oleh total hara yang melimpah.
            </p>
          </div>

          {/* Top Choice Analysis */}
          {topCrop && (
            <div className="space-y-1">
              <span className="font-semibold text-on-surface text-[11px] flex items-center gap-1.5">
                <CheckCircleIcon className="w-3.5 h-3.5 text-primary" />
                Alasan Pilihan Utama ({topCrop.crop_label}):
              </span>
              <p className="text-[11px] pl-5 leading-relaxed">{topCrop.reason}</p>
            </div>
          )}

          {/* Limiting Factors List */}
          <div className="space-y-1.5">
            <span className="font-semibold text-on-surface text-[11px] flex items-center gap-1.5">
              <ExclamationCircleIcon className="w-3.5 h-3.5 text-amber-600" />
              Faktor Pembatas Teridentifikasi:
            </span>
            {limitingFactors.length === 0 ? (
              <p className="text-[11px] pl-5 text-emerald-700">
                Tidak ada faktor pembatas berat pada kriteria hara utama.
              </p>
            ) : (
              <ul className="pl-5 space-y-1">
                {limitingFactors.map((factor, idx) => (
                  <li key={idx} className="text-[11px] list-disc">
                    <span className="font-medium text-on-surface">{factor.label} ({factor.parameter}):</span>{' '}
                    <span>{factor.explanation}</span>{' '}
                    {factor.value !== null && factor.value !== undefined && (
                      <span className="text-on-surface-variant/80">
                        (Nilai: {typeof factor.value === 'number' ? factor.value.toFixed(2) : factor.value}, Status: {factor.status_label})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

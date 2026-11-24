import React, { useState } from 'react';
import {
  SparklesIcon,
  ExclamationTriangleIcon,
  CheckBadgeIcon,
  WrenchScrewdriverIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '../../hooks/useAuth';
import { useHaraAnalysis } from '../../hooks/useHaraAnalysis';
import { ZoneBadge } from './ZoneBadge';
import { ConfidenceMeter } from './ConfidenceMeter';
import { WhyRecommendationAccordion } from './WhyRecommendationAccordion';
import { analysisService } from '../../services/analysis.service';
import { useToast } from '../../contexts/ToastContext';
import type { GeoJSONFeature, ReviewDecision } from '../../types/api.types';

interface AiRecommendationCardProps {
  selectedFeature: GeoJSONFeature | null;
}

export const AiRecommendationCard: React.FC<AiRecommendationCardProps> = ({
  selectedFeature,
}) => {
  const { role } = useAuth();
  const isExpert = role === 'expert' || role === 'admin';
  const { showToast } = useToast();

  const { analysis, isLoading, error, refetch } = useHaraAnalysis(selectedFeature);

  // State Form Review Pakar
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [reviewDecision, setReviewDecision] = useState<ReviewDecision>('validated');
  const [overrideZoneKey, setOverrideZoneKey] = useState<string>('high');
  const [reviewNote, setReviewNote] = useState<string>('');
  const [isSubmittingReview, setIsSubmittingReview] = useState(false);

  if (isLoading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 font-semibold text-on-surface">
          <SparklesIcon className="w-5 h-5 text-primary animate-spin" />
          <span>Menganalisis Lahan dengan AI...</span>
        </div>
        <div className="h-32 bg-surface-container-lowest border border-outline-variant/50 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 flex items-start gap-2.5">
        <ExclamationTriangleIcon className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="font-semibold">{error}</p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="text-rose-800 underline hover:text-rose-900 font-medium"
          >
            Coba lagi
          </button>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return null;
  }

  // Handle Kasus Data Tidak Lengkap / Sentinel Air
  if (analysis.status === 'insufficient_data') {
    return (
      <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-xl p-4 space-y-2 text-xs">
        <div className="flex items-center gap-2 font-semibold text-on-surface">
          <SparklesIcon className="w-5 h-5 text-primary" />
          <span>Analisis AI & Zona Kesuburan</span>
        </div>
        <p className="text-on-surface-variant leading-relaxed">{analysis.summary}</p>
        <p className="text-[11px] text-on-surface-variant/80 italic">
          *Poligon ini merupakan badan air atau area non-pertanian tanpa data hara terukur.
        </p>
      </div>
    );
  }

  const topCrop = analysis.crop_ranking[0];

  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFeature?.properties?.id) return;

    setIsSubmittingReview(true);
    try {
      await analysisService.createAnalysisReview(selectedFeature.properties.id, {
        decision: reviewDecision,
        zone_key: reviewDecision === 'overridden' ? overrideZoneKey : undefined,
        note: reviewNote.trim() || undefined,
      });
      showToast('Tinjauan pakar berhasil disimpan', 'success');
      setShowReviewForm(false);
      setReviewNote('');
      await refetch();
    } catch (err: unknown) {
      console.error('Failed to submit review:', err);
      showToast('Gagal menyimpan tinjauan pakar. Coba lagi.', 'error');
    } finally {
      setIsSubmittingReview(false);
    }
  };

  return (
    <div className="space-y-3.5">
      {/* Header AI & Zone */}
      <div className="bg-surface-container-lowest border border-outline-variant/60 rounded-xl p-3.5 space-y-3 shadow-xs">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <SparklesIcon className="w-4 h-4" />
            </span>
            <div>
              <h3 className="text-xs font-bold text-on-surface">Rekomendasi Cerdas AI</h3>
              <p className="text-[10px] text-on-surface-variant">
                Hybrid K-Means Clustered + Liebig Minimum Law
              </p>
            </div>
          </div>
          <ZoneBadge zone={analysis.zone} />
        </div>

        {/* Confidence Meter */}
        <ConfidenceMeter confidence={analysis.confidence} />

        {/* Banner Review Pakar */}
        {analysis.needs_expert_review && (
          <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200/80 flex items-start gap-2 text-[11px] text-amber-900">
            <ExclamationTriangleIcon className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold block">Perhatian: Memerlukan Review Pakar</span>
              <span className="text-amber-800 leading-snug">
                Data memiliki tingkat ketidakpastian atau faktor pembatas signifikan. Disarankan verifikasi lapangan dengan penyuluh pertanian.
              </span>
            </div>
          </div>
        )}

        {/* Ranking Komoditas Terurut */}
        <div className="space-y-2 pt-1">
          <div className="text-xs font-semibold text-on-surface flex items-center justify-between">
            <span>Peringkat Kesesuaian Komoditas</span>
            <span className="text-[10px] text-on-surface-variant font-normal">
              (Hukum Minimum Liebig)
            </span>
          </div>

          <div className="space-y-2">
            {analysis.crop_ranking.map((crop, index) => {
              const rank = index + 1;
              const isFirst = rank === 1;

              return (
                <div
                  key={crop.crop}
                  className={`p-2.5 rounded-xl border transition-all ${
                    isFirst
                      ? 'bg-primary/5 border-primary/30 ring-1 ring-primary/20'
                      : 'bg-surface-container-low border-outline-variant/40'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                          isFirst
                            ? 'bg-primary text-white'
                            : 'bg-surface-container-high text-on-surface-variant'
                        }`}
                      >
                        {rank}
                      </span>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-xs text-on-surface">
                            {crop.crop_label}
                          </span>
                          {isFirst && (
                            <span className="text-[10px] font-medium px-1.5 py-0.2 rounded bg-primary/20 text-primary">
                              Pilihan Utama
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-on-surface-variant">
                          Evaluasi: {crop.class} {crop.not_recommended ? '(Tidak Disarankan)' : '(Sesuai)'}
                        </span>
                      </div>
                    </div>

                    <div className="text-right">
                      <span
                        className={`inline-block text-xs font-bold px-2 py-0.5 rounded-md ${
                          crop.class === 'S1'
                            ? 'bg-emerald-100 text-emerald-800'
                            : crop.class === 'S2'
                            ? 'bg-green-100 text-green-800'
                            : crop.class === 'S3'
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-rose-100 text-rose-800'
                        }`}
                      >
                        Kelas {crop.class}
                      </span>
                    </div>
                  </div>

                  <p className="mt-1.5 text-[11px] text-on-surface-variant leading-relaxed">
                    {crop.reason}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Ameliorasi & Rekomendasi Pemupukan */}
        {analysis.amendments.length > 0 && (
          <div className="space-y-2 pt-1">
            <span className="text-xs font-semibold text-on-surface flex items-center gap-1.5">
              <WrenchScrewdriverIcon className="w-3.5 h-3.5 text-primary" />
              Saran Ameliorasi & Perbaikan Hara
            </span>
            <div className="space-y-1.5">
              {analysis.amendments.map((item, idx) => (
                <div
                  key={idx}
                  className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/40 space-y-1 text-[11px]"
                >
                  <div className="flex items-center justify-between font-semibold text-on-surface">
                    <span>
                      {item.title} ({item.parameter})
                    </span>
                    <span className="text-[10px] font-bold px-1.5 py-0.2 rounded uppercase bg-amber-100 text-amber-800">
                      {item.action_type}
                    </span>
                  </div>
                  <p className="text-on-surface-variant leading-snug">{item.recommendation}</p>
                  <div className="pt-0.5 text-[10px] text-primary font-medium">
                    📌 Catatan Dosis: {item.dosage_note}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Accordion Alasan Rekomendasi */}
        <WhyRecommendationAccordion
          topCrop={topCrop}
          limitingFactors={analysis.limiting_factors}
          summary={analysis.summary}
        />

        {/* Riwayat Tinjauan Pakar Terakhir */}
        {analysis.latest_review && (
          <div className="p-2 rounded-lg bg-blue-50/60 border border-blue-200/60 text-[11px] space-y-1 text-blue-900">
            <div className="flex items-center gap-1.5 font-semibold">
              <CheckBadgeIcon className="w-4 h-4 text-blue-700" />
              <span>Tinjauan Pakar Terakhir:</span>
            </div>
            <p className="pl-5 text-blue-800">
              Keputusan: <strong className="capitalize">{analysis.latest_review.decision}</strong>
              {analysis.latest_review.zone_key && (
                <span> (Zona: {analysis.latest_review.zone_key})</span>
              )}
              {analysis.latest_review.expert_name && (
                <span> oleh {analysis.latest_review.expert_name}</span>
              )}
            </p>
            {analysis.latest_review.note && (
              <p className="pl-5 italic text-[10px] text-blue-700">
                "{analysis.latest_review.note}"
              </p>
            )}
          </div>
        )}

        {/* Tombol & Form Review Khusus Pakar / Admin */}
        {isExpert && (
          <div className="pt-1 border-t border-outline-variant/40">
            {!showReviewForm ? (
              <button
                type="button"
                onClick={() => setShowReviewForm(true)}
                className="w-full py-1.5 px-3 rounded-lg border border-primary/40 text-primary hover:bg-primary/5 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
              >
                <CheckBadgeIcon className="w-4 h-4" />
                <span>Tinjau & Validasi Analisis (Pakar)</span>
              </button>
            ) : (
              <form onSubmit={handleReviewSubmit} className="space-y-2.5 p-3 rounded-xl bg-surface-container-low border border-outline-variant/60">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-on-surface">Validasi Hasil AI</span>
                  <button
                    type="button"
                    onClick={() => setShowReviewForm(false)}
                    className="text-[11px] text-on-surface-variant hover:text-on-surface"
                  >
                    Batal
                  </button>
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-on-surface block">
                    Keputusan Evaluasi:
                  </label>
                  <select
                    value={reviewDecision}
                    onChange={(e) => setReviewDecision(e.target.value as ReviewDecision)}
                    className="w-full text-xs p-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface"
                  >
                    <option value="validated">Setujui Rekomendasi AI (Validated)</option>
                    <option value="overridden">Koreksi Zona Kesuburan (Overridden)</option>
                  </select>
                </div>

                {reviewDecision === 'overridden' && (
                  <div className="space-y-1">
                    <label className="text-[11px] font-medium text-on-surface block">
                      Pilih Zona yang Benar:
                    </label>
                    <select
                      value={overrideZoneKey}
                      onChange={(e) => setOverrideZoneKey(e.target.value)}
                      className="w-full text-xs p-1.5 rounded-lg border border-outline-variant bg-surface text-on-surface"
                    >
                      <option value="high">Zona Subur Tinggi</option>
                      <option value="medium">Zona Subur Sedang</option>
                      <option value="low">Zona Subur Rendah</option>
                    </select>
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-on-surface block">
                    Catatan Pakar (Opsional):
                  </label>
                  <textarea
                    value={reviewNote}
                    onChange={(e) => setReviewNote(e.target.value)}
                    rows={2}
                    placeholder="Alasan validasi atau instruksi spesifik untuk penyuluh..."
                    className="w-full text-xs p-2 rounded-lg border border-outline-variant bg-surface text-on-surface"
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmittingReview}
                  className="w-full py-1.5 px-3 rounded-lg bg-primary text-white text-xs font-semibold hover:bg-primary-dark transition-colors disabled:opacity-50"
                >
                  {isSubmittingReview ? 'Menyimpan...' : 'Kirim Tinjauan Pakar'}
                </button>
              </form>
            )}
          </div>
        )}

        {/* Disclaimer Footer */}
        <p className="text-[10px] text-on-surface-variant/80 italic leading-snug pt-1 border-t border-outline-variant/30">
          {analysis.meta.disclaimer}
        </p>
      </div>
    </div>
  );
};

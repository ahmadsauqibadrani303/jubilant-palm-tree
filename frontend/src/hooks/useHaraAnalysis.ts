import { useState, useEffect, useCallback } from 'react';
import { analysisService } from '../services/analysis.service';
import type { GeoJSONFeature, AiAnalysisRead } from '../types/api.types';

export function useHaraAnalysis(selectedFeature: GeoJSONFeature | null) {
  const [analysis, setAnalysis] = useState<AiAnalysisRead | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalysis = useCallback(async () => {
    if (!selectedFeature?.properties?.id) {
      setAnalysis(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    const areaId = selectedFeature.properties.id;
    setIsLoading(true);
    setError(null);

    try {
      const data = await analysisService.getAreaAnalysis(areaId);
      setAnalysis(data);
    } catch (err: unknown) {
      console.error('Failed to load AI analysis:', err);
      setError('Gagal memuat rekomendasi AI untuk lahan ini.');
      setAnalysis(null);
    } finally {
      setIsLoading(false);
    }
  }, [selectedFeature?.properties?.id]);

  useEffect(() => {
    let isCancelled = false;

    if (!selectedFeature?.properties?.id) {
      setAnalysis(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    const areaId = selectedFeature.properties.id;
    setIsLoading(true);
    setError(null);

    analysisService
      .getAreaAnalysis(areaId)
      .then((data) => {
        if (!isCancelled) {
          setAnalysis(data);
          setIsLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!isCancelled) {
          console.error('Failed to fetch AI analysis:', err);
          setError('Gagal memuat rekomendasi AI untuk lahan ini.');
          setAnalysis(null);
          setIsLoading(false);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedFeature?.properties?.id]);

  return {
    analysis,
    isLoading,
    error,
    refetch: fetchAnalysis,
  };
}

export interface UserRead {
  id: number;
  email: string;
  full_name: string;
  role: 'user' | 'expert' | 'admin';
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
}

export interface HaraProperties {
  id: number;
  name: string;
  ph_rata2: number;
  n_rata2: number;
  p_rata2: number;
  k_rata2: number;
  slope__?: string;
  texture_of?: string;
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: any;
  properties: HaraProperties;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export interface AdvisoryRead {
  id: number;
  hara_area_id: number;
  title: string;
  content: string;
  category: string;
  is_active: boolean;
  created_at: string;
}

export interface SavedRegionPoint {
  type: 'Point';
  coordinates: [number, number];
}

export interface SavedRegionRead {
  id: number;
  hara_area_id: number;
  selected_point: SavedRegionPoint;
  label: string;
  area: GeoJSONFeature;
  created_at: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserRegister {
  email: string;
  password: string;
  full_name: string;
}

export interface HaraAreaUpdate {
  name?: string | null;
  ph_rata2?: number | null;
  n_rata2?: number | null;
  p_rata2?: number | null;
  k_rata2?: number | null;
  slope__?: string | null;
  texture_of?: string | null;
}

export interface AdvisoryCreate {
  title: string;
  content: string;
  category?: 'soil' | 'fertilizer' | 'general' | null;
  is_active?: boolean;
}

export interface AdvisoryUpdate {
  title?: string | null;
  content?: string | null;
  category?: 'soil' | 'fertilizer' | 'general' | null;
  is_active?: boolean | null;
}

export interface GlossaryTerm {
  id: number;
  term: string;
  definition: string;
  created_at: string;
  updated_at?: string;
}

export interface GlossaryCreate {
  term: string;
  definition: string;
}

export interface GlossaryUpdate {
  term?: string;
  definition?: string;
}

export interface HaraAreaCreate {
  geometry: any;
  properties: {
    name?: string | null;
    ph_rata2?: number | null;
    n_rata2?: number | null;
    p_rata2?: number | null;
    k_rata2?: number | null;
    slope__?: string | null;
    texture_of?: string | null;
  };
}

export interface Averages {
  ph: number;
  n: number;
  p: number;
  k: number;
}

export interface PhDistribution {
  sangat_masam: number;
  masam: number;
  sedikit_masam: number;
  netral: number;
  sedikit_alkalis: number;
  alkalis: number;
}

export interface CriticalArea {
  id: number;
  name: string;
  value: number;
  parameter: string;
}

export interface MacroAnalyticsRead {
  averages: Averages;
  ph_distribution: PhDistribution;
  critical_areas: CriticalArea[];
}

export interface DiagnosisFactor {
  key: string;
  label: string;
  value: number | string | null;
  status: string;
  status_label: string;
  severity: 'info' | 'watch' | 'attention' | 'critical';
  message: string;
}

export interface DiagnosisRecommendation {
  priority: number;
  category: string;
  title: string;
  action: string;
  reason: string;
}

export interface CropSuitability {
  crop: string;
  class: 'S1' | 'S2' | 'S3' | 'N';
  limiting_factors: string[];
  ph_class: 'S1' | 'S2' | 'S3' | 'N';
  n_class: 'S1' | 'S2' | 'S3' | 'N';
  p_class: 'S1' | 'S2' | 'S3' | 'N';
  k_class: 'S1' | 'S2' | 'S3' | 'N';
}

export interface HaraDiagnosisRead {
  rule_set_version: string;
  status: 'ready' | 'insufficient_data';
  summary: string;
  area: any;
  factors: DiagnosisFactor[];
  recommendations: DiagnosisRecommendation[];
  crop_suitabilities: CropSuitability[];
}

export interface HaraAreaChangeRead {
  id: number;
  hara_area_id: number;
  user_id: number;
  action: 'create' | 'update' | string;
  changed_fields: Record<string, any>;
  created_at: string;
  user: UserRead;
  area_name?: string | null;
}

// ==========================================
// AI Analysis & Zoning Types (FASE 3 & 4)
// ==========================================

export type ConfidenceCategory = 'tinggi' | 'sedang' | 'rendah';
export type AnalysisStatus = 'ready' | 'insufficient_data';
export type FactorSeverity = 'info' | 'watch' | 'attention' | 'critical';
export type ReviewDecision = 'validated' | 'overridden';

export interface ZoneInfo {
  zone_key: 'high' | 'medium' | 'low' | 'unknown' | string;
  zone_label: string;
  cluster_id: number;
  dist_to_centroid?: number | null;
  dist_to_second?: number | null;
  is_overridden: boolean;
  override_note?: string | null;
}

export interface LimitingFactorDetail {
  parameter: string;
  label: string;
  value: number | string | null;
  status: string;
  status_label: string;
  severity: FactorSeverity;
  explanation: string;
}

export interface CropRankingItem {
  crop: string;
  crop_label: string;
  class: 'S1' | 'S2' | 'S3' | 'N';
  limiting_factors: string[];
  reason: string;
  not_recommended: boolean;
  ph_class: string;
  n_class: string;
  p_class: string;
  k_class: string;
}

export interface AmendmentAdvice {
  parameter: string;
  action_type: string;
  title: string;
  recommendation: string;
  input_category: string;
  dosage?: string | null;
  dosage_note: string;
  reason: string;
}

export interface ConfidenceBreakdown {
  cluster_margin: number;
  data_completeness: number;
  rule_zone_agreement: number;
  boundary_proximity_penalty: number;
  weights: Record<string, number>;
}

export interface ConfidenceInfo {
  score: number;
  category: ConfidenceCategory;
  breakdown: ConfidenceBreakdown;
}

export interface AnalysisMeta {
  model_version: string;
  rule_set_version: string;
  generated_at: string;
  disclaimer: string;
}

export interface AnalysisReviewRead {
  id: number;
  area_id: number;
  expert_id: number;
  expert_name?: string | null;
  decision: string;
  zone_key?: string | null;
  note?: string | null;
  created_at: string;
}

export interface AnalysisReviewCreate {
  decision: ReviewDecision;
  zone_key?: string | null;
  note?: string | null;
}

export interface AiAnalysisRead {
  area_id: number;
  status: AnalysisStatus;
  summary: string;
  needs_expert_review: boolean;
  zone?: ZoneInfo | null;
  limiting_factors: LimitingFactorDetail[];
  crop_ranking: CropRankingItem[];
  amendments: AmendmentAdvice[];
  confidence?: ConfidenceInfo | null;
  latest_review?: AnalysisReviewRead | null;
  meta: AnalysisMeta;
}

export interface ZoneSummaryItem {
  area_id: number;
  zone_key: string;
  zone_label: string;
  confidence_category: string;
}

export interface ReviewQueueItem {
  area_id: number;
  name: string;
  zone_key: string;
  zone_label: string;
  confidence_score?: number | null;
  confidence_category: string;
  reasons: string[];
  latest_review?: AnalysisReviewRead | null;
}

// ── API Response Types ──────────────────────────────────────────

export interface DashboardOverview {
  events: { total: number };
  trends: { total: number; rising: number };
  recommendations: { total: number; high_priority: number };
  alerts: { total: number; open: number };
  sources: { total: number; active: number };
}

export interface TrendItem {
  id: number;
  topic: string;
  category: string;
  score: number;
  confidence: number;
  direction: string;
  event_count: number;
  growth_rate: number;
  source: string;
  first_seen: string;
  last_seen: string;
  ai_summary: string | null;
}

export interface TrendDetail extends TrendItem {
  metadata: Record<string, unknown>;
  recommendations: { id: number; title: string; priority: string; confidence: number }[];
  alerts: { id: number; title: string; severity: string; status: string }[];
  related_events: { id: number; title: string; source: string }[];
}

export interface RecommendationItem {
  id: number;
  title: string;
  body: string;
  category: string;
  priority: string;
  confidence: number;
  status: string;
  trend_id: number | null;
  created_at: string;
  ai_enhancement: string | null;
}

export interface AlertItem {
  id: number;
  title: string;
  alert_type: string;
  severity: string;
  status: string;
  body: string;
  trend_id: number | null;
  created_at: string;
  acknowledged_at: string | null;
}

export interface SourceItem {
  id: number;
  name: string;
  source_type: string;
  status: string;
  enabled: boolean;
  config_json: Record<string, unknown>;
  items_fetched: number;
  items_normalized: number;
  failure_count: number;
  last_sync_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface LlmGeneration {
  id: number;
  entity_type: string;
  entity_id: number | null;
  prompt_template: string;
  provider: string;
  model: string;
  output_text: string | null;
  tokens_used: number;
  error: string | null;
  generated_at: string;
}

export interface DigestItem {
  id: number;
  title: string;
  summary: string | null;
  top_trends: { id: number; topic: string; score: number }[];
  top_recommendations: { id: number; title: string; priority: string }[];
  key_risks: string[];
  stats: Record<string, number>;
  created_at: string;
}

export interface ActivityEvent {
  id: number;
  source: string;
  event_type: string;
  title: string;
  ingested_at: string;
}

export interface DemoStatus {
  tenant_id: string;
  events: number;
  trends: number;
  recommendations: number;
  alerts: number;
  sources: number;
  recent_runs: { id: number; action: string; status: string; started_at: string; result: Record<string, unknown> }[];
}

export interface PaginatedResponse<T> {
  total: number;
  items: T[];
}

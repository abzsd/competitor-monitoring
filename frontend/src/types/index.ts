export interface Competitor {
  _id: string;
  name: string;
  slug: string;
  domain: string;
  industry: string;
  description: string;
  tags: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
  source_count: number;
  recent_change_count: number;
}

export interface Source {
  _id: string;
  competitor_id: string;
  competitor_name: string;
  url: string;
  page_type: string;
  scrape_method: string;
  schedule_group: string;
  discovery_method: string;
  is_active: boolean;
  last_scraped_at: string | null;
  last_changed_at: string | null;
  consecutive_failures: number;
  created_at: string;
  updated_at: string;
}

export interface Change {
  _id: string;
  source_id: string;
  competitor_id: string;
  competitor_name: string;
  source_url: string;
  detected_at: string;
  change_type: string;
  severity: string;
  summary: string;
  text_diff?: string;
  structured_diff?: Record<string, unknown[]>;
  snapshot_before_id?: string;
  snapshot_after_id?: string;
  analysis_id?: string;
  is_analyzed: boolean;
  is_alerted: boolean;
  created_at: string;
}

export interface Analysis {
  _id: string;
  competitor_id: string;
  competitor_name: string;
  change_ids: string[];
  analysis_type: string;
  generated_at: string;
  content: {
    // Standard analysis fields
    summary?: string;
    impact_assessment?: string;
    actionable_insights?: string[];
    category?: string;
    confidence?: number;
    // Investigation report fields (from investigate.py)
    what_happened?: string;
    why_it_matters?: string;
    market_context?: string;
    recommended_response?: string;
    key_facts?: string[];
    sources_cited?: string[];
    risk_level?: string;
    // News search origin fields
    search_queries?: string[];
    articles_analyzed?: number;
  };
  created_at: string;
}

export interface Alert {
  _id: string;
  analysis_id: string | null;
  change_ids: string[];
  competitor_id: string;
  competitor_name: string;
  channel: string;
  severity: string;
  subject: string;
  body: string;
  sent_at: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

export interface Partnership {
  _id: string;
  competitor_id: string;
  competitor_name: string;
  partner_name: string;
  partnership_type: string;
  source_url: string;
  discovered_at: string;
  description: string;
  confidence: number;
  status: string;
  created_at: string;
}

export interface CompetitorActivity {
  name: string;
  slug: string;
  activity_score: number;
  source_count: number;
  change_count_7d: number;
}

export interface NewsItem {
  _id: string;
  competitor_id: string;
  competitor_name: string;
  url: string;
  title: string;
  source_domain: string;
  content_snippet: string;
  search_category: string;
  relevance_score: number;
  discovered_at: string;
  published_date: string | null;
  created_at: string;
}

export interface DashboardStats {
  total_competitors: number;
  total_sources: number;
  active_sources: number;
  failing_sources: number;
  total_changes_7d: number;
  total_changes_30d: number;
  changes_by_severity: Record<string, number>;
  changes_by_type: Record<string, number>;
  alerts_last_24h: number;
  news_items_7d: number;
  recent_changes: Change[];
  recent_alerts: Alert[];
  competitor_activity: CompetitorActivity[];
}

export interface ActivityLogEntry {
  _id: string;
  scan_id: string;
  event: string;
  detail: string;
  status: 'info' | 'success' | 'warning' | 'error';
  timestamp: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

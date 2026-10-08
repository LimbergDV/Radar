/** Configuración por fuente y resultado de sincronización. */

import type { SourceId } from './source.model';

export interface YouTubeConfig {
  keywords: string[];
  channel_ids: string[];
  languages: string[];
  max_results: number;
  last_search_at: string | null;
}

export interface GoogleNewsConfig {
  q: string;
  hl: string;
  gl: string;
  ceid: string;
  when: string;
  site: string;
  intitle: string;
  max_results: number;
  days_window: number;
  last_search_at: string | null;
}

export interface GitHubConfig {
  keywords: string[];
  days_active: number;
  min_stars: number;
  min_forks: number;
  require_license: boolean;
  selected_topics: string[];
  selected_languages: string[];
  max_results: number;
  last_search_at: string | null;
}

/** Respuesta de `POST /api/{fuente}/sync`. */
export interface SyncResult {
  status: string;
  source: SourceId;
  items_synced: number;
  duration_seconds: number | null;
  message?: string | null;
}

export interface HealthStatus {
  status: string;
  env: string;
  scheduler_running: boolean;
  sync_interval_minutes: number;
}
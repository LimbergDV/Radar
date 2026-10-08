/** Feed unificado y estadísticas del dashboard (`/api/feed`). */

import type { SourceId } from './source.model';

/** Item normalizado: el backend ya aplanó las tres fuentes a esta forma. */
export interface FeedItem {
  source: SourceId;
  source_id: string;
  title: string;
  url: string;
  published_at: string;
  description: string;
  image_url: string | null;
  author: string | null;
  language: string | null;
  /** Métricas propias de cada fuente; la card las lee sin saber el origen. */
  stats: {
    views?: number;
    likes?: number;
    comments?: number;
    duration_seconds?: number;
    stars?: number;
    forks?: number;
    issues?: number;
    has_content?: boolean;
  };
  extra: {
    channel_id?: string;
    has_transcript?: boolean;
    source_url?: string;
    content_fetched?: boolean;
    topics?: string[];
    license?: string | null;
    has_readme?: boolean;
  };
}

export interface FeedResponse {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  items: FeedItem[];
}

export interface SourceStats {
  total: number;
  last_sync_at: string | null;
  latest_item_at: string | null;
}

export interface NamedCount {
  name?: string;
  language?: string;
  count: number;
}

export interface FeedStats {
  total_items: number;
  youtube: SourceStats;
  news: SourceStats;
  github: SourceStats;
  top_news_sources: NamedCount[];
  top_github_languages: NamedCount[];
  generated_at: string;
}
/** Tipos de las fuentes. Reflejan 1:1 los DTOs del backend
 *  (`/api/youtube`, `/api/news`, `/api/github`, `/api/papers`). */

export type SourceId = 'youtube' | 'news' | 'github' | 'papers';

export interface YouTubeVideoSummary {
  id: string;
  title: string;
  channel: string;
  channel_id: string;
  published_at: string;
  url: string;
  thumbnail_url: string;
  views: number;
  likes: number;
  comments: number;
  duration_seconds: number;
  language: string;
  synced_at: string;
}

export interface YouTubeVideoDetail extends YouTubeVideoSummary {
  transcript: string;
}

/** Cuota del fallback de transcripciones (RapidAPI). */
export interface TranscriptFallbackStatus {
  enabled: boolean;
  used_by_app: number;
  app_budget: number;
  /** null cuando aún no se ha llamado al proveedor en este proceso. */
  remaining: number | null;
  provider_limit: number | null;
  month: string;
}

/** Cobertura de transcripciones del feed y cuota disponible. */
export interface TranscriptStatus {
  total_videos: number;
  with_transcript: number;
  missing_transcript: number;
  coverage_percent: number;
  fallback: TranscriptFallbackStatus;
}

/** Resultado de una pasada de relleno de transcripciones. */
export interface TranscriptBackfillResult {
  status: string;
  source: string;
  candidates: number;
  filled: number;
  failed: number;
  sources: Record<string, number>;
  failures: Record<string, number>;
  quota: TranscriptFallbackStatus;
}

export interface GoogleNewsArticleSummary {
  id: string;
  title: string;
  link: string;
  pub_date: string;
  source_name: string;
  source_url: string;
  image_url: string | null;
  language: string;
}

export interface GoogleNewsArticleDetail extends GoogleNewsArticleSummary {
  content: string | null;
  content_fetched: boolean;
  fetched_at: string;
}

export interface GitHubRepoSummary {
  id: number;
  name: string;
  full_name: string;
  html_url: string;
  description: string;
  stargazers_count: number;
  forks_count: number;
  open_issues_count: number;
  watchers_count: number;
  language: string;
  license: string | null;
  topics: string[];
  owner_avatar_url: string | null;
  homepage: string | null;
  updated_at: string;
  synced_at: string;
}

export interface GitHubRepoDetail extends GitHubRepoSummary {
  readme: string;
  size_kb: number;
  default_branch: string;
}
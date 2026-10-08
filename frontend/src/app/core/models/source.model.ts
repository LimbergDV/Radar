/** Tipos de las tres fuentes. Reflejan 1:1 los DTOs del backend
 *  (`/api/youtube`, `/api/news`, `/api/github`). */

export type SourceId = 'youtube' | 'news' | 'github';

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
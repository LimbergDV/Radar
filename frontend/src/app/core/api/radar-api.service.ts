import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import type {
  FeedResponse,
  FeedStats,
  GitHubConfig,
  GitHubRepoDetail,
  GitHubRepoSummary,
  GoogleNewsArticleDetail,
  GoogleNewsArticleSummary,
  GoogleNewsConfig,
  HealthStatus,
  SourceId,
  SyncResult,
  YouTubeConfig,
  YouTubeVideoDetail,
  YouTubeVideoSummary,
} from '../models';

/** Filtros de listado que el backend acepta. */
export interface ListParams {
  limit?: number;
  offset?: number;
}

export interface FeedQuery extends ListParams {
  source?: SourceId | null;
  language?: string | null;
  q?: string | null;
}

/** Parámetros de paginación que se traducen a query string. Descarta null/undefined/vacío. */
function toParams(options: object): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(options)) {
    if (value !== null && value !== undefined && value !== '') {
      params = params.set(key, String(value));
    }
  }
  return params;
}

/** Gateway único hacia el backend. Ningún componente usa HttpClient directo:
 *  si mañana cambia una ruta o la forma de la respuesta, se toca este archivo. */
@Injectable({ providedIn: 'root' })
export class RadarApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  // ── Feed y dashboard ──

  getFeed(query: FeedQuery = {}): Observable<FeedResponse> {
    return this.http.get<FeedResponse>(`${this.base}/feed`, {
      params: toParams(query),
    });
  }

  getStats(): Observable<FeedStats> {
    return this.http.get<FeedStats>(`${this.base}/feed/stats`);
  }

  getHealth(): Observable<HealthStatus> {
    // /health vive fuera del prefijo /api.
    return this.http.get<HealthStatus>(`${this.base.replace(/\/api$/, '')}/health`);
  }

  // ── YouTube ──

  getVideos(options: ListParams & { language?: string | null } = {}): Observable<YouTubeVideoSummary[]> {
    return this.http.get<YouTubeVideoSummary[]>(`${this.base}/youtube/videos`, {
      params: toParams(options),
    });
  }

  getVideo(id: string): Observable<YouTubeVideoDetail> {
    return this.http.get<YouTubeVideoDetail>(`${this.base}/youtube/videos/${id}`);
  }

  syncYouTube(): Observable<SyncResult> {
    return this.http.post<SyncResult>(`${this.base}/youtube/sync`, null);
  }

  getYouTubeConfig(): Observable<YouTubeConfig> {
    return this.http.get<YouTubeConfig>(`${this.base}/youtube/config`);
  }

  updateYouTubeConfig(config: YouTubeConfig): Observable<YouTubeConfig> {
    return this.http.put<YouTubeConfig>(`${this.base}/youtube/config`, config);
  }

  // ── Google News ──

  getArticles(
    options: ListParams & { language?: string | null; source?: string | null; since_days?: number | null } = {},
  ): Observable<GoogleNewsArticleSummary[]> {
    return this.http.get<GoogleNewsArticleSummary[]>(`${this.base}/news/articles`, {
      params: toParams(options),
    });
  }

  getArticle(id: string): Observable<GoogleNewsArticleDetail> {
    return this.http.get<GoogleNewsArticleDetail>(`${this.base}/news/articles/${id}`);
  }

  syncNews(): Observable<SyncResult> {
    return this.http.post<SyncResult>(`${this.base}/news/sync`, null);
  }

  getNewsConfig(): Observable<GoogleNewsConfig> {
    return this.http.get<GoogleNewsConfig>(`${this.base}/news/config`);
  }

  updateNewsConfig(config: GoogleNewsConfig): Observable<GoogleNewsConfig> {
    return this.http.put<GoogleNewsConfig>(`${this.base}/news/config`, config);
  }

  // ── GitHub ──

  getRepos(
    options: ListParams & { language?: string | null; topic?: string | null; min_stars?: number | null } = {},
  ): Observable<GitHubRepoSummary[]> {
    return this.http.get<GitHubRepoSummary[]>(`${this.base}/github/repos`, {
      params: toParams(options),
    });
  }

  getRepo(id: number): Observable<GitHubRepoDetail> {
    return this.http.get<GitHubRepoDetail>(`${this.base}/github/repos/${id}`);
  }

  syncGitHub(): Observable<SyncResult> {
    return this.http.post<SyncResult>(`${this.base}/github/sync`, null);
  }

  getGitHubConfig(): Observable<GitHubConfig> {
    return this.http.get<GitHubConfig>(`${this.base}/github/config`);
  }

  updateGitHubConfig(config: GitHubConfig): Observable<GitHubConfig> {
    return this.http.put<GitHubConfig>(`${this.base}/github/config`, config);
  }
}
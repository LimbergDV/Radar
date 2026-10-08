import { computed, inject, Injectable, signal } from '@angular/core';
import { map, type Observable } from 'rxjs';

import { RadarApiService } from '../../core/api/radar-api.service';
import type { FeedItem, FeedResponse, SourceId } from '../../core/models';
import { createListResource } from '../../shared/state/list-resource';

export type SourceFilter = SourceId | 'all';

interface FeedFilters {
  source: SourceFilter;
  language: string;
  query: string;
}

const EMPTY_FILTERS: FeedFilters = { source: 'all', language: '', query: '' };

/** Estado del feed unificado: filtros + paginación, en un solo sitio. */
@Injectable()
export class FeedStore {
  private readonly api = inject(RadarApiService);

  readonly filters = signal<FeedFilters>({ ...EMPTY_FILTERS });

  private readonly resource = createListResource<FeedItem>(
    (offset, limit) =>
      this.api
        .getFeed({ ...this.toQuery(), limit, offset })
        // El backend responde con { items, has_more }; el recurso pide { items, hasMore }.
        .pipe(map((response: FeedResponse) => ({
          items: response.items,
          hasMore: response.has_more,
        }))),
  );

  readonly items = this.resource.items;
  readonly loading = this.resource.loading;
  readonly error = this.resource.error;
  readonly hasMore = this.resource.hasMore;

  /** Idiomas presentes en lo ya cargado, para los chips de filtro. */
  readonly languages = computed(() => {
    const found = new Set<string>();
    for (const item of this.items()) {
      if (item.language) {
        found.add(item.language);
      }
    }
    return [...found].sort();
  });

  load(): void {
    this.resource.load();
  }

  loadMore(): void {
    this.resource.loadMore();
  }

  apply(partial: Partial<FeedFilters>): void {
    // Cualquier cambio de filtro reinicia la paginación.
    this.filters.set({ ...this.filters(), ...partial });
    this.resource.load();
  }

  reset(): void {
    this.filters.set({ ...EMPTY_FILTERS });
    this.resource.load();
  }

  private toQuery(): { source: SourceId | null; language: string | null; q: string | null } {
    const { source, language, query } = this.filters();
    return {
      source: source === 'all' ? null : source,
      language: language || null,
      q: query.trim() || null,
    };
  }
}
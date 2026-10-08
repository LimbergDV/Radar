import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import { map } from 'rxjs';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import type { YouTubeVideoSummary } from '../../core/models';
import { CardSkeletonComponent } from '../../shared/components/card-skeleton/card-skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SyncButtonComponent } from '../../shared/components/sync-button/sync-button.component';
import { CompactNumberPipe, DurationPipe } from '../../shared/pipes/format.pipes';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';
import { createListResource } from '../../shared/state/list-resource';

const LANGUAGES = [
  { value: '', label: 'Todos' },
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'Inglés' },
];

@Component({
  selector: 'app-youtube-list',
  standalone: true,
  imports: [
    RouterLink,
    LucideAngularModule,
    CompactNumberPipe,
    DurationPipe,
    TimeAgoPipe,
    PageHeaderComponent,
    EmptyStateComponent,
    CardSkeletonComponent,
    SyncButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './youtube-list.component.html',
  styleUrl: './youtube-list.component.scss',
})
export class YoutubeListComponent {
  private readonly api = inject(RadarApiService);

  protected readonly languages = LANGUAGES;
  protected readonly language = signal('');

  protected readonly resource = createListResource<YouTubeVideoSummary>(
    (offset, limit) =>
      this.api
        .getVideos({ limit, offset, language: this.language() || null })
        // Este endpoint devuelve un array plano sin total: hay más si viene lleno.
        .pipe(mapPage(limit)),
  );

  protected readonly items = this.resource.items;
  protected readonly loading = this.resource.loading;
  protected readonly error = this.resource.error;
  protected readonly hasMore = this.resource.hasMore;

  constructor() {
    this.resource.load();
  }

  protected setLanguage(value: string): void {
    this.language.set(value);
    this.resource.load();
  }

  protected onSynced(): void {
    this.resource.load();
  }
}

function mapPage(limit: number) {
  return map((items: YouTubeVideoSummary[]) => ({
    items,
    hasMore: items.length === limit,
  }));
}
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import { map } from 'rxjs';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import type { GoogleNewsArticleSummary } from '../../core/models';
import { CardSkeletonComponent } from '../../shared/components/card-skeleton/card-skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SyncButtonComponent } from '../../shared/components/sync-button/sync-button.component';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';
import { createListResource } from '../../shared/state/list-resource';

const WINDOWS = [
  { value: 1, label: '24 h' },
  { value: 3, label: '3 días' },
  { value: 7, label: '7 días' },
  { value: 30, label: '30 días' },
];

@Component({
  selector: 'app-news-list',
  standalone: true,
  imports: [
    RouterLink,
    LucideAngularModule,
    TimeAgoPipe,
    PageHeaderComponent,
    EmptyStateComponent,
    CardSkeletonComponent,
    SyncButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './news-list.component.html',
  styleUrl: './news-list.component.scss',
})
export class NewsListComponent {
  private readonly api = inject(RadarApiService);

  protected readonly windows = WINDOWS;
  protected readonly days = signal(1);

  protected readonly resource = createListResource<GoogleNewsArticleSummary>(
    (offset, limit) =>
      this.api
        .getArticles({ limit, offset, since_days: this.days() })
        .pipe(map((items) => ({ items, hasMore: items.length === limit }))),
  );

  protected readonly items = this.resource.items;
  protected readonly loading = this.resource.loading;
  protected readonly error = this.resource.error;
  protected readonly hasMore = this.resource.hasMore;

  constructor() {
    this.resource.load();
  }

  protected setWindow(days: number): void {
    this.days.set(days);
    this.resource.load();
  }

  protected onSynced(): void {
    this.resource.load();
  }
}
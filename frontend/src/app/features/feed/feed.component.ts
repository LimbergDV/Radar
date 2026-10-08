import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import type { FeedStats, SourceId } from '../../core/models';
import { CardSkeletonComponent } from '../../shared/components/card-skeleton/card-skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { FeedCardComponent } from '../../shared/components/feed-card/feed-card.component';
import { SourceBadgeComponent } from '../../shared/components/source-badge/source-badge.component';
import { StatTileComponent } from '../../shared/components/stat-tile/stat-tile.component';
import { SyncButtonComponent } from '../../shared/components/sync-button/sync-button.component';
import { CompactNumberPipe } from '../../shared/pipes/format.pipes';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';
import { FeedStore } from './feed.store';
import type { SourceFilter } from './feed.store';

@Component({
  selector: 'app-feed',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    LucideAngularModule,
    CompactNumberPipe,
    TimeAgoPipe,
    FeedCardComponent,
    SourceBadgeComponent,
    StatTileComponent,
    EmptyStateComponent,
    CardSkeletonComponent,
    SyncButtonComponent,
  ],
  providers: [FeedStore],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feed.component.html',
  styleUrl: './feed.component.scss',
})
export class FeedComponent {
  private readonly api = inject(RadarApiService);
  protected readonly store = inject(FeedStore);

  protected readonly stats = signal<FeedStats | null>(null);
  protected readonly search = signal('');

  private readonly timeAgo = new TimeAgoPipe();

  protected readonly sources: { value: SourceFilter; label: string; icon: string }[] = [
    { value: 'all', label: 'Todo', icon: 'LayoutGrid' },
    { value: 'youtube', label: 'YouTube', icon: 'Youtube' },
    { value: 'news', label: 'Noticias', icon: 'Newspaper' },
    { value: 'github', label: 'GitHub', icon: 'Github' },
  ];

  private searchTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.store.load();
    this.loadStats();
  }

  private loadStats(): void {
    this.api.getStats().subscribe((stats) => this.stats.set(stats));
  }

  /** "Último: hace 3 h" o "Último: sin datos". */
  protected lastLabel(date: string | null): string {
    const relative = date ? this.timeAgo.transform(date) : '';
    return relative ? `Último: ${relative}` : 'Último: sin datos';
  }

  protected setSource(source: SourceFilter): void {
    this.store.apply({ source });
  }

  protected setLanguage(language: string): void {
    const current = this.store.filters().language;
    this.store.apply({ language: current === language ? '' : language });
  }

  /** Debounce: no conviene pedir en cada tecla. */
  protected onSearch(value: string): void {
    this.search.set(value);
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.store.apply({ query: value }), 350);
  }

  protected onSynced(): void {
    this.store.load();
    this.loadStats();
  }
}
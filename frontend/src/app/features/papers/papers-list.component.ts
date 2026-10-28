import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import { map } from 'rxjs';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import type { PaperSummary } from '../../core/models';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SyncButtonComponent } from '../../shared/components/sync-button/sync-button.component';
import { CardSkeletonComponent } from '../../shared/components/card-skeleton/card-skeleton.component';
import { CompactNumberPipe } from '../../shared/pipes/format.pipes';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';
import { createListResource } from '../../shared/state/list-resource';

type Order = 'recent' | 'top';

const WINDOWS: { value: number | null; label: string }[] = [
  { value: 7, label: '7 días' },
  { value: 30, label: '30 días' },
  { value: 90, label: '90 días' },
  { value: null, label: 'Todo' },
];

@Component({
  selector: 'app-papers-list',
  standalone: true,
  imports: [
    RouterLink,
    LucideAngularModule,
    CompactNumberPipe,
    TimeAgoPipe,
    PageHeaderComponent,
    EmptyStateComponent,
    CardSkeletonComponent,
    SyncButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './papers-list.component.html',
  styleUrl: './papers-list.component.scss',
})
export class PapersListComponent {
  private readonly api = inject(RadarApiService);

  protected readonly windows = WINDOWS;
  protected readonly days = signal<number | null>(7);
  protected readonly order = signal<Order>('recent');
  protected readonly search = signal('');

  protected readonly resource = createListResource<PaperSummary>(
    (offset, limit) =>
      this.api
        .getPapers({
          limit,
          offset,
          since_days: this.days(),
          order: this.order(),
          q: this.search().trim() || null,
        })
        .pipe(map((items) => ({ items, hasMore: items.length === limit }))),
  );

  protected readonly items = this.resource.items;
  protected readonly loading = this.resource.loading;
  protected readonly error = this.resource.error;
  protected readonly hasMore = this.resource.hasMore;

  private searchTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.resource.load();
  }

  protected setDays(days: number | null): void {
    this.days.set(days);
    this.resource.load();
  }

  protected setOrder(order: Order): void {
    if (this.order() === order) {
      return;
    }
    this.order.set(order);
    this.resource.load();
  }

  /** Debounce: buscar no debe disparar una request por tecla. */
  protected onSearch(value: string): void {
    this.search.set(value);
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.resource.load(), 400);
  }

  protected onSynced(): void {
    this.resource.load();
  }

  protected authorLine(paper: PaperSummary): string {
    return paper.organization || paper.authors[0] || 'Hugging Face';
  }
}

import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';
import { map } from 'rxjs';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import type { GitHubRepoSummary } from '../../core/models';
import { CardSkeletonComponent } from '../../shared/components/card-skeleton/card-skeleton.component';
import { EmptyStateComponent } from '../../shared/components/empty-state/empty-state.component';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SyncButtonComponent } from '../../shared/components/sync-button/sync-button.component';
import { CompactNumberPipe } from '../../shared/pipes/format.pipes';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';
import { createListResource } from '../../shared/state/list-resource';

@Component({
  selector: 'app-github-list',
  standalone: true,
  imports: [
    FormsModule,
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
  templateUrl: './github-list.component.html',
  styleUrl: './github-list.component.scss',
})
export class GithubListComponent {
  private readonly api = inject(RadarApiService);

  protected readonly language = signal('');
  protected readonly topic = signal('');

  protected readonly resource = createListResource<GitHubRepoSummary>(
    (offset, limit) =>
      this.api
        .getRepos({
          limit,
          offset,
          language: this.language() || null,
          topic: this.topic() || null,
        })
        .pipe(map((items) => ({ items, hasMore: items.length === limit }))),
  );

  protected readonly items = this.resource.items;
  protected readonly loading = this.resource.loading;
  protected readonly error = this.resource.error;
  protected readonly hasMore = this.resource.hasMore;

  private topicTimer?: ReturnType<typeof setTimeout>;

  constructor() {
    this.resource.load();
  }

  protected setLanguage(language: string): void {
    this.language.set(language);
    this.resource.load();
  }

  /** Debounce: escribir un topic no debe disparar una request por tecla. */
  protected onTopic(value: string): void {
    this.topic.set(value);
    clearTimeout(this.topicTimer);
    this.topicTimer = setTimeout(() => this.resource.load(), 400);
  }

  protected onSynced(): void {
    this.resource.load();
  }
}
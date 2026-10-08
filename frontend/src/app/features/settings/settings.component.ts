import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LucideAngularModule } from 'lucide-angular';

import { RadarApiService } from '../../core/api/radar-api.service';
import type {
  GitHubConfig,
  GoogleNewsConfig,
  YouTubeConfig,
} from '../../core/models';
import { ToastService } from '../../core/notifications/toast.service';
import { PageHeaderComponent } from '../../shared/components/page-header/page-header.component';
import { SyncButtonComponent } from '../../shared/components/sync-button/sync-button.component';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';

type Tab = 'youtube' | 'news' | 'github';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    FormsModule,
    LucideAngularModule,
    TimeAgoPipe,
    PageHeaderComponent,
    SyncButtonComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {
  private readonly api = inject(RadarApiService);
  private readonly toasts = inject(ToastService);

  protected readonly tab = signal<Tab>('youtube');
  protected readonly saving = signal<Tab | null>(null);

  protected readonly youtube = signal<YouTubeConfig | null>(null);
  protected readonly news = signal<GoogleNewsConfig | null>(null);
  protected readonly github = signal<GitHubConfig | null>(null);

  /** Campos de texto que en la API son arrays; aquí se editan separados por coma. */
  protected readonly ytKeywords = signal('');
  protected readonly ytChannels = signal('');
  protected readonly newsKeywords = signal('');
  protected readonly ghKeywords = signal('');
  protected readonly ghTopics = signal('');
  protected readonly ghLanguages = signal('');

  constructor() {
    this.loadAll();
  }

  protected setTab(tab: Tab): void {
    this.tab.set(tab);
  }

  private loadAll(): void {
    this.api.getYouTubeConfig().subscribe((config) => {
      this.youtube.set(config);
      this.ytKeywords.set(config.keywords.join(', '));
      this.ytChannels.set(config.channel_ids.join(', '));
    });

    this.api.getNewsConfig().subscribe((config) => {
      this.news.set(config);
      this.newsKeywords.set(config.q);
    });

    this.api.getGitHubConfig().subscribe((config) => {
      this.github.set(config);
      this.ghKeywords.set(config.keywords.join(', '));
      this.ghTopics.set(config.selected_topics.join(', '));
      this.ghLanguages.set(config.selected_languages.join(', '));
    });
  }

  /** Convierte "a, b , c" en ["a","b","c"]. */
  private splitList(value: string): string[] {
    return value
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean);
  }

  protected saveYouTube(): void {
    const current = this.youtube();
    if (!current) {
      return;
    }
    this.saving.set('youtube');

    const payload: YouTubeConfig = {
      ...current,
      keywords: this.splitList(this.ytKeywords()),
      channel_ids: this.splitList(this.ytChannels()),
    };

    this.api.updateYouTubeConfig(payload).subscribe({
      next: (saved) => {
        this.youtube.set(saved);
        this.ytKeywords.set(saved.keywords.join(', '));
        this.ytChannels.set(saved.channel_ids.join(', '));
        this.saving.set(null);
        this.toasts.success('Configuración de YouTube guardada. Pulsa Sincronizar para aplicarla.');
      },
      error: () => this.saving.set(null),
    });
  }

  protected saveNews(): void {
    const current = this.news();
    if (!current) {
      return;
    }
    this.saving.set('news');

    const payload: GoogleNewsConfig = { ...current, q: this.newsKeywords() };

    this.api.updateNewsConfig(payload).subscribe({
      next: (saved) => {
        this.news.set(saved);
        this.newsKeywords.set(saved.q);
        this.saving.set(null);
        this.toasts.success('Configuración de noticias guardada.');
      },
      error: () => this.saving.set(null),
    });
  }

  protected saveGitHub(): void {
    const current = this.github();
    if (!current) {
      return;
    }
    this.saving.set('github');

    const payload: GitHubConfig = {
      ...current,
      keywords: this.splitList(this.ghKeywords()),
      selected_topics: this.splitList(this.ghTopics()),
      selected_languages: this.splitList(this.ghLanguages()),
    };

    this.api.updateGitHubConfig(payload).subscribe({
      next: (saved) => {
        this.github.set(saved);
        this.ghKeywords.set(saved.keywords.join(', '));
        this.ghTopics.set(saved.selected_topics.join(', '));
        this.ghLanguages.set(saved.selected_languages.join(', '));
        this.saving.set(null);
        this.toasts.success('Configuración de GitHub guardada.');
      },
      error: () => this.saving.set(null),
    });
  }

  protected onSynced(): void {
    this.loadAll();
  }

  /** Actualizadores de un campo. Los templates no pueden hacer spread de objeto,
   *  así que cada cambio pasa por aquí. */
  protected setYouTube(patch: Partial<YouTubeConfig>): void {
    this.youtube.update((config) => (config ? { ...config, ...patch } : config));
  }

  protected setNews(patch: Partial<GoogleNewsConfig>): void {
    this.news.update((config) => (config ? { ...config, ...patch } : config));
  }

  protected setGitHub(patch: Partial<GitHubConfig>): void {
    this.github.update((config) => (config ? { ...config, ...patch } : config));
  }

  /** "Última sincronización: …" o "nunca". */
  protected lastSync(date: string | null): string {
    if (!date) {
      return 'nunca';
    }
    return this.timeAgo.transform(date) || 'hace un momento';
  }

  private readonly timeAgo = new TimeAgoPipe();
}
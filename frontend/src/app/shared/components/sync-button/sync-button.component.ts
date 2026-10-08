import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import { RadarApiService } from '../../../core/api/radar-api.service';
import type { SourceId, SyncResult } from '../../../core/models';
import { ToastService } from '../../../core/notifications/toast.service';

/** Botón de sincronización manual. Recibe la fuente; si no se indica, sincroniza todas. */
@Component({
  selector: 'app-sync-button',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button class="sync" type="button" [class.sync--ghost]="variant() === 'ghost'"
            [disabled]="running()" (click)="run()">
      <lucide-icon [name]="running() ? 'Loader' : 'RefreshCw'"
                    [size]="14"
                    [class.sync__spin]="running()"
                    aria-hidden="true" />
      <span>{{ label() }}</span>
    </button>
  `,
  styles: `
    .sync {
      display: inline-flex;
      align-items: center;
      gap: var(--space-8);
      padding: var(--space-8) var(--space-16);
      border: 1px solid transparent;
      border-radius: var(--radius-control);
      background: var(--color-blueprint-blue);
      color: #fff;
      font-size: var(--text-body-sm);
      font-weight: var(--weight-semibold);
      cursor: pointer;
      transition: background 120ms var(--ease);

      &:hover:not(:disabled) {
        background: var(--color-blueprint-blue-dark);
      }

      &:disabled {
        cursor: progress;
        opacity: 0.65;
      }
    }

    // Variante secundaria: sin relleno, para no competir con el CTA azul.
    .sync--ghost {
      background: transparent;
      border-color: var(--color-fog);
      color: var(--color-ink-black);

      &:hover:not(:disabled) {
        background: var(--color-paper);
        border-color: var(--color-slate);
      }
    }

    .sync__spin {
      animation: spin 900ms linear infinite;
    }

    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }
  `,
})
export class SyncButtonComponent {
  private readonly api = inject(RadarApiService);
  private readonly toasts = inject(ToastService);

  /** Fuente a sincronizar. `null` = las tres. */
  readonly source = input<SourceId | null>(null);
  readonly variant = input<'solid' | 'ghost'>('solid');
  readonly label = input<string>('Sincronizar');

  protected readonly running = signal(false);

  /** Llamado tras cada sync para que el padre recargue su lista. */
  readonly synced = input<((result: SyncResult) => void) | null>(null);

  private endpoints: Record<SourceId, () => ReturnType<RadarApiService['syncYouTube']>> = {
    youtube: () => this.api.syncYouTube(),
    news: () => this.api.syncNews(),
    github: () => this.api.syncGitHub(),
  };

  async run(): Promise<void> {
    if (this.running()) {
      return;
    }
    this.running.set(true);

    const sources: SourceId[] = this.source() ? [this.source() as SourceId] : ['youtube', 'news', 'github'];

    try {
      const results: SyncResult[] = [];

      // En serie y no en paralelo: las APIs externas tienen rate limit y un
      // burst simultáneo lo agota.
      for (const source of sources) {
        results.push(await new Promise<SyncResult>((resolve, reject) => {
          this.endpoints[source]().subscribe({ next: resolve, error: reject });
        }));
      }

      const total = results.reduce((sum, result) => sum + result.items_synced, 0);
      const notas = results
        .map((result) => result.message)
        .filter((message): message is string => Boolean(message));

      this.toasts.success(
        `Sync completado: ${total} ${total === 1 ? 'item' : 'items'} en ${sources.length} ${
          sources.length === 1 ? 'fuente' : 'fuentes'
        }.`,
      );
      for (const nota of notas) {
        this.toasts.info(nota);
      }

      for (const result of results) {
        this.synced()?.(result);
      }
    } catch {
      // El interceptor ya notificó el error; aquí sólo liberamos el botón.
    } finally {
      this.running.set(false);
    }
  }
}
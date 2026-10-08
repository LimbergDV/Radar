import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { RadarIconName } from '../../../core/icons/icons';
import { LucideAngularModule } from 'lucide-angular';

/** Métrica suelta para el dashboard: número grande + etiqueta + detalle. */
@Component({
  selector: 'app-stat-tile',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="tile">
      <div class="tile__head">
        @if (icon()) {
          <lucide-icon [name]="icon()!" [size]="14" class="tile__icon" aria-hidden="true" />
        }
        <span class="tile__label">{{ label() }}</span>
      </div>
      <p class="tile__value">{{ value() }}</p>
      @if (hint()) {
        <p class="u-meta tile__hint">{{ hint() }}</p>
      }
    </div>
  `,
  styles: `
    .tile {
      background: var(--color-canvas);
      border: 1px solid var(--color-fog);
      border-radius: var(--radius-card);
      padding: var(--space-16);
    }

    .tile__head {
      display: flex;
      align-items: center;
      gap: var(--space-8);
      color: var(--color-slate);
    }

    .tile__value {
      margin-top: var(--space-8);
      font-size: var(--text-heading-sm);
      font-weight: var(--weight-semibold);
      letter-spacing: var(--tracking-tight);
      color: var(--color-ink-black);
    }

    .tile__hint {
      margin-top: var(--space-4);
    }
  `,
})
export class StatTileComponent {
  readonly label = input.required<string>();
  readonly value = input.required<string | number>();
  readonly hint = input<string>('');
  readonly icon = input<RadarIconName | null>(null);
}
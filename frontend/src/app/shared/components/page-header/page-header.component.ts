import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';

import type { RadarIconName } from '../../../core/icons/icons';

/** Cabecera de página: título, descripción y hueco para la acción principal. */
@Component({
  selector: 'app-page-header',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <header class="head">
      <div class="head__text">
        <div class="head__eyebrow">
          @if (icon()) {
            <lucide-icon [name]="icon()!" [size]="14" aria-hidden="true" />
          }
          @if (eyebrow()) {
            <span class="u-mono-label">{{ eyebrow() }}</span>
          }
        </div>
        <h1>{{ title() }}</h1>
        @if (description()) {
          <p class="head__desc">{{ description() }}</p>
        }
      </div>
      <div class="head__action">
        <ng-content />
      </div>
    </header>
  `,
  styles: `
    .head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--space-20);
      padding-bottom: var(--space-20);
      margin-bottom: var(--space-20);
      border-bottom: 1px solid var(--color-fog);
    }

    .head__eyebrow {
      display: flex;
      align-items: center;
      gap: var(--space-8);
      margin-bottom: var(--space-8);
      color: var(--color-slate);
    }

    .head__desc {
      margin-top: var(--space-8);
      max-width: 60ch;
      font-size: var(--text-body-sm);
      color: var(--color-slate);
    }

    .head__action {
      flex: 0 0 auto;
    }
  `,
})
export class PageHeaderComponent {
  readonly title = input.required<string>();
  readonly description = input<string>('');
  readonly eyebrow = input<string>('');
  readonly icon = input<RadarIconName | null>(null);
}
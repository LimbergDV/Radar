import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { RadarIconName } from '../../../core/icons/icons';
import { LucideAngularModule } from 'lucide-angular';

/** Cuando no hay nada que mostrar: explica por qué y qué hacer. */
@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [LucideAngularModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="empty">
      <lucide-icon [name]="icon()" [size]="20" class="empty__icon" aria-hidden="true" />
      <h3 class="empty__title">{{ title() }}</h3>
      @if (message()) {
        <p class="empty__message">{{ message() }}</p>
      }
    </div>
  `,
  styles: `
    .empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: var(--space-8);
      padding: var(--space-48) var(--space-20);
      text-align: center;
      background: var(--color-canvas);
      border: 1px dashed var(--color-fog);
      border-radius: var(--radius-card);
    }

    .empty__icon {
      color: var(--color-fog);
    }

    .empty__title {
      font-size: var(--text-subheading);
    }

    .empty__message {
      max-width: 44ch;
      font-size: var(--text-body-sm);
      color: var(--color-slate);
    }
  `,
})
export class EmptyStateComponent {
  readonly title = input.required<string>();
  readonly message = input<string>('');
  readonly icon = input.required<RadarIconName>();
}
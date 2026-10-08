import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { SourceId } from '../../../core/models';

/** Placeholder con el mismo esqueleto que la card real, para evitar saltos. */
@Component({
  selector: 'app-card-skeleton',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="skeleton" aria-hidden="true">
      <div class="skeleton__thumb" [class]="'skeleton__thumb skeleton__thumb--' + source()"></div>
      <div class="skeleton__body">
        <div class="skeleton__line skeleton__line--sm"></div>
        <div class="skeleton__line"></div>
        <div class="skeleton__line"></div>
        <div class="skeleton__line skeleton__line--xs"></div>
      </div>
    </div>
  `,
  styles: `
    .skeleton {
      display: flex;
      gap: var(--space-16);
      padding: var(--space-16);
      background: var(--color-canvas);
      border: 1px solid var(--color-fog);
      border-radius: var(--radius-card);
    }

    .skeleton__thumb {
      flex: 0 0 64px;
      height: 64px;
      border-radius: var(--radius-control);
      background: var(--color-paper);
    }

    .skeleton__thumb--youtube {
      background: var(--color-stone);
    }

    .skeleton__body {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: var(--space-8);
    }

    .skeleton__line {
      height: 10px;
      border-radius: 3px;
      background: var(--color-paper);
      animation: pulse 1.4s var(--ease) infinite;
    }

    .skeleton__line--sm {
      width: 32%;
      height: 8px;
    }

    .skeleton__line--xs {
      width: 22%;
      height: 8px;
    }

    @keyframes pulse {
      0%,
      100% {
        opacity: 1;
      }
      50% {
        opacity: 0.5;
      }
    }
  `,
})
export class CardSkeletonComponent {
  readonly source = input<SourceId>('news');
}
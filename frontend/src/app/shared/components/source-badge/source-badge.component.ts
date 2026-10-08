import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { SourceId } from '../../../core/models';

/** Etiqueta de origen. Un punto del color del tema + nombre en mayúsculas. */
const LABELS: Record<SourceId, string> = {
  youtube: 'YouTube',
  news: 'Noticias',
  github: 'GitHub',
};

@Component({
  selector: 'app-source-badge',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <span class="badge" [class]="'badge badge--' + source()">
      <span class="badge__dot" aria-hidden="true"></span>
      {{ label() }}
    </span>
  `,
  styles: `
    :host {
      display: inline-block;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: var(--radius-control);
      background: var(--color-paper);
      font-size: var(--text-caption);
      font-weight: var(--weight-medium);
      letter-spacing: var(--tracking-caps);
      text-transform: uppercase;
      color: var(--color-slate);
    }

    .badge__dot {
      width: 4px;
      height: 4px;
      border-radius: 50%;
      background: currentColor;
    }

    .badge--youtube {
      color: var(--color-blueprint-blue);
    }

    .badge--news {
      color: var(--color-ink-black);
    }

    .badge--github {
      color: var(--color-carbon);
    }
  `,
})
export class SourceBadgeComponent {
  readonly source = input.required<SourceId>();

  label(): string {
    return LABELS[this.source()];
  }
}
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import type { FeedItem } from '../../../core/models';
import { CompactNumberPipe, DurationPipe } from '../../pipes/format.pipes';
import { TimeAgoPipe } from '../../pipes/time-ago.pipe';
import { SourceBadgeComponent } from '../source-badge/source-badge.component';

/**
 * Card del feed. Un solo componente para las tres fuentes: el backend ya
 * normalizó los campos, así que aquí sólo cambia qué métricas se muestran.
 */
@Component({
  selector: 'app-feed-card',
  standalone: true,
  imports: [
    RouterLink,
    LucideAngularModule,
    CompactNumberPipe,
    DurationPipe,
    TimeAgoPipe,
    SourceBadgeComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feed-card.component.html',
  styleUrl: './feed-card.component.scss',
})
export class FeedCardComponent {
  readonly item = input.required<FeedItem>();

  protected readonly itemLink = computed(() => this.detailLink());

  /** Métricas visibles para la fuente del item. */
  protected readonly metrics = computed(() => {
    const { source, stats } = this.item();

    if (source === 'youtube') {
      return [
        { icon: 'Eye', value: stats.views ?? 0 },
        { icon: 'Star', value: stats.likes ?? 0 },
        { icon: 'Hash', value: stats.comments ?? 0 },
      ];
    }

    if (source === 'github') {
      return [
        { icon: 'Star', value: stats.stars ?? 0 },
        { icon: 'GitFork', value: stats.forks ?? 0 },
        { icon: 'CircleAlert', value: stats.issues ?? 0 },
      ];
    }

    return [];
  });

  /** Duración formateada (solo YouTube). */
  protected readonly duration = computed(() => {
    const seconds = this.item().stats.duration_seconds ?? 0;
    return seconds > 0 ? new DurationPipe().transform(seconds) : '';
  });

  protected readonly hasThumbnail = computed(() => {
    const { source, image_url } = this.item();
    if (source === 'github') {
      return false; // el avatar es un círculo, no va en el slot de la miniatura
    }
    return Boolean(image_url);
  });

  /** Etiqueta corta de la fuente: idioma del video, medio de la nota, lenguaje del repo. */
  protected readonly tagline = computed(() => {
    const { source, author, language, extra } = this.item();

    if (source === 'github') {
      return language || 'GitHub';
    }
    if (source === 'news') {
      return author || 'Noticias';
    }
    return language || '';
  });

  /** GitHub sí tiene detalle propio; noticias y YouTube también. */
  protected detailLink(): string[] {
    const { source, source_id } = this.item();
    if (source === 'github') {
      return ['/github', source_id];
    }
    if (source === 'news') {
      return ['/news', source_id];
    }
    return ['/youtube', source_id];
  }
}
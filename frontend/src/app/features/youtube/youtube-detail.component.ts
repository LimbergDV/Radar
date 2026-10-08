import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, type SafeResourceUrl } from '@angular/platform-browser';
import { LucideAngularModule } from 'lucide-angular';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import { useRouteResource } from '../../core/hooks/use-route-resource';
import type { YouTubeVideoDetail } from '../../core/models';
import { CompactNumberPipe, DurationPipe } from '../../shared/pipes/format.pipes';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';

/** Detalle del video: player embebido, métricas y transcripción completa. */
@Component({
  selector: 'app-youtube-detail',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, CompactNumberPipe, DurationPipe, TimeAgoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './youtube-detail.component.html',
  styleUrl: './youtube-detail.component.scss',
})
export class YoutubeDetailComponent {
  private readonly api = inject(RadarApiService);
  private readonly sanitizer = inject(DomSanitizer);

  /** `withComponentInputBinding` inyecta el :id de la ruta como signal. */
  readonly id = input.required<string>();

  protected readonly resource = useRouteResource(this.id, (id) => this.api.getVideo(id));

  /** YouTube usa el dominio sin cookies, que no expone datos de seguimiento. */
  protected readonly embedUrl = computed<SafeResourceUrl | null>(() => {
    const video = this.resource.data();
    if (!video) {
      return null;
    }
    // El id viene de la ruta y el host es fijo, así que no hay superficie de
    // inyección; Angular exige SafeResourceUrl para usarlo como [src].
    return this.sanitizer.bypassSecurityTrustResourceUrl(
      `https://www.youtube-nocookie.com/embed/${encodeURIComponent(video.id)}`,
    );
  });

  /** Título del video, o el id si viniera vacío. Evita un `title` sin nada. */
  protected videoTitle(video: YouTubeVideoDetail): string {
    return video.title || video.id;
  }

  /** El fetcher escribe este texto cuando no pudo obtener la transcripción. */
  protected hasTranscript(text: string): boolean {
    return Boolean(text?.trim()) && text.trim() !== 'Transcripción no disponible';
  }

  protected wordCount(text: string): number {
    return text.trim().split(/\s+/).filter(Boolean).length;
  }
}
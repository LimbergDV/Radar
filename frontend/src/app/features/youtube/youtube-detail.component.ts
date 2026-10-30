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

  /** Minutos de lectura a ~200 palabras/minuto, mínimo 1. */
  protected readingMinutes(text: string): number {
    return Math.max(1, Math.round(this.wordCount(text) / 200));
  }

  /**
   * La transcripción llega como un único bloque sin saltos de línea: YouTube la
   * entrega así. Partirla en párrafos es lo que la hace legible; sin esto son
   * miles de caracteres en un solo muro de texto.
   */
  protected readonly transcriptParagraphs = computed<string[]>(() => {
    const text = this.resource.data()?.transcript ?? '';
    return this.hasTranscript(text) ? splitIntoParagraphs(text) : [];
  });
}

/** Longitud objetivo de cada párrafo, en caracteres. */
const PARAGRAPH_TARGET = 700;

/**
 * Divide un texto plano en párrafos, cortando por frases.
 *
 * Si el texto no trae puntuación (pasa con subtítulos automáticos), cortar por
 * frases daría un único párrafo enorme: en ese caso se agrupa por palabras.
 */
export function splitIntoParagraphs(text: string, target = PARAGRAPH_TARGET): string[] {
  const clean = text.replace(/\s+/g, ' ').trim();
  if (!clean) {
    return [];
  }

  const sentences = clean.match(/[^.!?…]+[.!?…]+["'»)]*\s*/g) ?? [];
  if (sentences.length < 3) {
    return chunkByWords(clean, target);
  }

  const paragraphs: string[] = [];
  let current = '';

  for (const sentence of sentences) {
    if (current && current.length + sentence.length > target) {
      paragraphs.push(current.trim());
      current = '';
    }
    current += sentence;
  }

  const tail = current.trim();
  if (tail) {
    paragraphs.push(tail);
  }
  return paragraphs;
}

function chunkByWords(text: string, target: number): string[] {
  const words = text.split(' ');
  const chunks: string[] = [];
  let current: string[] = [];
  let length = 0;

  for (const word of words) {
    if (current.length && length + word.length + 1 > target) {
      chunks.push(current.join(' '));
      current = [];
      length = 0;
    }
    current.push(word);
    length += word.length + 1;
  }

  if (current.length) {
    chunks.push(current.join(' '));
  }
  return chunks;
}

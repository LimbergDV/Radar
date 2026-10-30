import { ChangeDetectionStrategy, Component, computed, inject, input } from '@angular/core';
import { DomSanitizer, type SafeHtml } from '@angular/platform-browser';
import { LucideAngularModule } from 'lucide-angular';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import { useRouteResource } from '../../core/hooks/use-route-resource';
import { renderReadme } from '../../shared/markdown/readme-renderer';
import { CompactNumberPipe } from '../../shared/pipes/format.pipes';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';

const README_MAX_CHARS = 40_000;

@Component({
  selector: 'app-github-detail',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, CompactNumberPipe, TimeAgoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './github-detail.component.html',
  styleUrl: './github-detail.component.scss',
})
export class GithubDetailComponent {
  private readonly api = inject(RadarApiService);
  private readonly sanitizer = inject(DomSanitizer);

  readonly id = input.required<number>();

  protected readonly resource = useRouteResource(this.id, (id) => this.api.getRepo(id));

  /**
   * README ya convertido de markdown a HTML y saneado.
   *
   * Es `computed` y no un signal con caché manual a propósito: así, al cambiar
   * de repo en la misma vista, se recalcula en vez de dejar el anterior.
   *
   * `bypassSecurityTrustHtml` es seguro aquí porque `renderReadme` pasa el HTML
   * por DOMPurify antes de devolverlo.
   */
  protected readonly readmeHtml = computed<SafeHtml | null>(() => {
    const repo = this.resource.data();
    if (!repo?.readme) {
      return null;
    }
    const html = renderReadme(repo.readme.slice(0, README_MAX_CHARS), repo);
    return this.sanitizer.bypassSecurityTrustHtml(html);
  });
}

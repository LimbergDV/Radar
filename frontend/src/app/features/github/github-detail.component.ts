import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { DomSanitizer, type SafeHtml } from '@angular/platform-browser';
import { LucideAngularModule } from 'lucide-angular';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import { useRouteResource } from '../../core/hooks/use-route-resource';
import type { GitHubRepoDetail } from '../../core/models';
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

  /** Vista previa del README en texto plano: sin HTML ni estilos inline. */
  protected readonly readmePreview = signal<SafeHtml | null>(null);

  /**
   * El README llega como markdown crudo y lo mostramos preformateado. Antes de
   * inyectarlo se escapan `& < >`, así que un `<script>` en el README se
   * muestra como texto en vez de ejecutarse.
   */
  protected readmeOf(repo: GitHubRepoDetail): SafeHtml | null {
    if (!repo.readme) {
      return null;
    }
    if (!this.readmePreview()) {
      this.readmePreview.set(
        this.sanitizer.bypassSecurityTrustHtml(
          repo.readme
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .slice(0, README_MAX_CHARS),
        ),
      );
    }
    return this.readmePreview();
  }
}
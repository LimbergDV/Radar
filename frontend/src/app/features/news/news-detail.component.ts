import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import { useRouteResource } from '../../core/hooks/use-route-resource';
import type { GoogleNewsArticleDetail } from '../../core/models';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';

@Component({
  selector: 'app-news-detail',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, TimeAgoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './news-detail.component.html',
  styleUrl: './news-detail.component.scss',
})
export class NewsDetailComponent {
  private readonly api = inject(RadarApiService);

  readonly id = input.required<string>();

  protected readonly resource = useRouteResource(this.id, (id) => this.api.getArticle(id));

  /** El medio real, si se pudo guardar; si no, la portada que trajo el RSS. */
  protected sourceLink(article: GoogleNewsArticleDetail): string {
    return article.source_url || article.link;
  }
}
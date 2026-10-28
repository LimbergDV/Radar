import { ChangeDetectionStrategy, Component, inject, input } from '@angular/core';
import { LucideAngularModule } from 'lucide-angular';
import { RouterLink } from '@angular/router';

import { RadarApiService } from '../../core/api/radar-api.service';
import { useRouteResource } from '../../core/hooks/use-route-resource';
import type { PaperDetail } from '../../core/models';
import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';

@Component({
  selector: 'app-papers-detail',
  standalone: true,
  imports: [RouterLink, LucideAngularModule, TimeAgoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './papers-detail.component.html',
  styleUrl: './papers-detail.component.scss',
})
export class PapersDetailComponent {
  private readonly api = inject(RadarApiService);

  readonly id = input.required<string>();

  protected readonly resource = useRouteResource(this.id, (id) => this.api.getPaper(id));

  protected authorLine(paper: PaperDetail): string {
    return paper.organization || paper.authors[0] || 'Hugging Face';
  }

  protected modelUrl(id: string): string {
    return `https://huggingface.co/${id}`;
  }

  protected datasetUrl(id: string): string {
    return `https://huggingface.co/datasets/${id}`;
  }

  protected spaceUrl(id: string): string {
    return `https://huggingface.co/spaces/${id}`;
  }
}

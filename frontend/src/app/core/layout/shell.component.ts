import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { TimeAgoPipe } from '../../shared/pipes/time-ago.pipe';
import { RadarApiService } from '../api/radar-api.service';
import { ToastService } from '../notifications/toast.service';

interface NavItem {
  path: string;
  label: string;
  icon: string;
  source: 'youtube' | 'news' | 'github' | null;
}

const NAV: NavItem[] = [
  { path: '/feed', label: 'Feed', icon: 'LayoutGrid', source: null },
  { path: '/youtube', label: 'YouTube', icon: 'Youtube', source: 'youtube' },
  { path: '/news', label: 'Noticias', icon: 'Newspaper', source: 'news' },
  { path: '/github', label: 'GitHub', icon: 'Github', source: 'github' },
  { path: '/settings', label: 'Configuración', icon: 'Settings', source: null },
];

/** Shell: sidebar fija + columna principal. Aquí viven también los toasts. */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, LucideAngularModule, TimeAgoPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './shell.component.html',
  styleUrl: './shell.component.scss',
})
export class ShellComponent {
  private readonly api = inject(RadarApiService);
  protected readonly toasts = inject(ToastService);

  protected readonly nav = NAV;
  protected readonly online = signal<boolean | null>(null);

  constructor() {
    this.checkHealth();
    setInterval(() => this.checkHealth(), 30_000);
  }

  private checkHealth(): void {
    this.api.getHealth().subscribe({
      next: () => this.online.set(true),
      error: () => this.online.set(false),
    });
  }
}
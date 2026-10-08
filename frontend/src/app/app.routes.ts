import { Routes } from '@angular/router';

/**
 * Shell con sidebar y las páginas dentro. Cada feature va lazy: el bundle inicial
 * sólo trae el shell, y cada vista se descarga al navegar a ella.
 */
export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./core/layout/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'feed' },

      {
        path: 'feed',
        title: 'Feed · Radar',
        loadComponent: () => import('./features/feed/feed.component').then((m) => m.FeedComponent),
      },

      {
        path: 'youtube',
        title: 'YouTube · Radar',
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/youtube/youtube-list.component').then((m) => m.YoutubeListComponent),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/youtube/youtube-detail.component').then(
                (m) => m.YoutubeDetailComponent,
              ),
          },
        ],
      },

      {
        path: 'news',
        title: 'Noticias · Radar',
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/news/news-list.component').then((m) => m.NewsListComponent),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/news/news-detail.component').then((m) => m.NewsDetailComponent),
          },
        ],
      },

      {
        path: 'github',
        title: 'GitHub · Radar',
        children: [
          {
            path: '',
            loadComponent: () =>
              import('./features/github/github-list.component').then((m) => m.GithubListComponent),
          },
          {
            path: ':id',
            loadComponent: () =>
              import('./features/github/github-detail.component').then((m) => m.GithubDetailComponent),
          },
        ],
      },

      {
        path: 'settings',
        title: 'Configuración · Radar',
        loadComponent: () =>
          import('./features/settings/settings.component').then((m) => m.SettingsComponent),
      },
    ],
  },

  { path: '**', redirectTo: 'feed' },
];
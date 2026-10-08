import { provideHttpClient, withInterceptors } from '@angular/common/http';
import {
  ApplicationConfig,
  importProvidersFrom,
  provideZoneChangeDetection,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';
import { LucideAngularModule } from 'lucide-angular';

import { routes } from './app.routes';
import { apiErrorInterceptor } from './core/api/api-error.interceptor';
import { RADAR_ICONS } from './core/icons/icons';

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(
      routes,
      // Los componentes leen el parámetro de ruta como input, sin ActivatedRoute.
      withComponentInputBinding(),
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled' }),
    ),
    provideHttpClient(withInterceptors([apiErrorInterceptor])),
    // Registro global de iconos: los componentes standalone sólo importan
    // LucideAngularModule y usan `name="..."`.
    importProvidersFrom(LucideAngularModule.pick(RADAR_ICONS)),
  ],
};
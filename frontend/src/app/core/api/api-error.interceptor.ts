import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpInterceptorFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { ToastService } from '../notifications/toast.service';

/**
 * Normaliza los errores del backend en mensajes que la UI pueda mostrar y
 * dispara un aviso global. El resto de la app nunca ve un HttpErrorResponse.
 */
export const apiErrorInterceptor: HttpInterceptorFn = (
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
) => {
  const toasts = inject(ToastService);

  return next(request).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse)) {
        return throwError(() => error);
      }

      // Un 4xx de validación suele traer `detail` del backend (422 de FastAPI).
      const detail = extractDetail(error);
      toasts.error(detail);
      return throwError(() => new Error(detail));
    }),
  );
};

function extractDetail(error: HttpErrorResponse): string {
  if (error.status === 0) {
    return 'No hay conexión con el backend. ¿Está corriendo en el puerto 8000?';
  }

  const body = error.error as { detail?: unknown } | null;
  const detail = body?.detail;

  if (typeof detail === 'string') {
    return detail;
  }

  // FastAPI devuelve lista de errores cuando falla la validación de un body.
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? first.loc.at(-1) : null;
    return field ? `${field}: ${first.msg ?? 'valor inválido'}` : (first.msg ?? 'Datos inválidos');
  }

  if (error.status === 404) {
    return 'No encontrado.';
  }

  return `Error ${error.status} del servidor.`;
}
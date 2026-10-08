import { DestroyRef, effect, inject, signal, type InputSignal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, type Observable, catchError, finalize, tap } from 'rxjs';

/**
 * Estado de un recurso que depende de un parámetro de ruta (`:id`).
 *
 * Reemplaza el `effect()` + `subscribe()` a mano de cada detalle, y cubre los
 * dos detalles que siempre se olvidan:
 *
 * - no repetir la llamada cuando el efecto corre sin cambio real;
 * - propagar `loading` con `finalize`, para que un error no deje el spinner
 *   clavado.
 */
export function useRouteResource<T, I extends string | number = string>(
  id: InputSignal<I>,
  fetchOne: (id: I) => Observable<T>,
) {
  const destroyRef = inject(DestroyRef);

  const data = signal<T | null>(null);
  const loading = signal(true);
  const error = signal<string | null>(null);

  let requestedId: I | undefined;

  effect(() => {
    const current = id();

    if (requestedId === current) {
      return;
    }
    requestedId = current;

    loading.set(true);
    error.set(null);
    data.set(null);

    fetchOne(current)
      .pipe(
        takeUntilDestroyed(destroyRef),
        tap((value) => data.set(value)),
        catchError((cause: unknown) => {
          error.set(describe(cause));
          return EMPTY;
        }),
        finalize(() => loading.set(false)),
      )
      .subscribe();
  });

  return {
    data: data.asReadonly(),
    loading: loading.asReadonly(),
    error: error.asReadonly(),
  } as const;
}

/** Traduce el fallo de HttpClient a algo presentable. */
function describe(cause: unknown): string {
  if (typeof cause === 'object' && cause !== null && 'status' in cause) {
    const status = (cause as { status: number }).status;
    if (status === 404) {
      return 'No encontrado.';
    }
    return `Error ${status} del servidor.`;
  }
  return 'No se pudo cargar.';
}
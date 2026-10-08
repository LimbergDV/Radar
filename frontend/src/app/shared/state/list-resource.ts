import { DestroyRef, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, type Observable, catchError, finalize, tap, type Subscription } from 'rxjs';

/** Respuesta paginada normalizada que produce cada fetch. */
export interface Page<T> {
  items: T[];
  hasMore: boolean;
}

export interface ListResourceOptions {
  pageSize?: number;
}

/**
 * Estado de carga reutilizable para las páginas de listado.
 *
 * Evita repetir `loading`/`error`/`items` en el feed, en las tres vistas por
 * fuente y en el dashboard. Se declara con un `fetch` y se consume con
 * `load()`, `loadMore()` y `reload()`.
 */
export function createListResource<T>(
  fetchPage: (offset: number, limit: number) => Observable<Page<T>>,
  options: ListResourceOptions = {},
) {
  const destroyRef = inject(DestroyRef);
  const pageSize = options.pageSize ?? 20;

  const items = signal<T[]>([]);
  const loading = signal(false);
  const error = signal<string | null>(null);
  const hasMore = signal(false);

  let offset = 0;
  let inFlight: Subscription | null = null;

  function run(nextOffset: number, append: boolean): void {
    // Cancelamos la petición anterior: al cambiar de filtro rápidamente evita
    // que llegue una respuesta vieja y pise la nueva.
    inFlight?.unsubscribe();
    loading.set(true);
    error.set(null);

    inFlight = fetchPage(nextOffset, pageSize)
      .pipe(
        takeUntilDestroyed(destroyRef),
        tap((page) => {
          items.update((current) => (append ? [...current, ...page.items] : page.items));
          offset = nextOffset;
          hasMore.set(page.hasMore);
        }),
        catchError(() => {
          // El interceptor de errores ya disparó el toast; aquí sólo dejamos el
          // estado listo para que la vista explique qué pasó.
          error.set('No se pudieron cargar los datos.');
          return EMPTY;
        }),
        finalize(() => loading.set(false)),
      )
      .subscribe();
  }

  return {
    items,
    loading,
    error,
    hasMore,

    /** Primera carga: reemplaza la lista. */
    load: () => run(0, false),

    /** Carga la página siguiente y la concatena. */
    loadMore: () => {
      if (loading() || !hasMore()) {
        return;
      }
      run(offset + pageSize, true);
    },

    /** Repite la carga conservando los filtros actuales. */
    reload: () => run(offset, false),

    /** Vacía el estado (al cambiar de fuente o de búsqueda). */
    clear: () => {
      inFlight?.unsubscribe();
      items.set([]);
      offset = 0;
      hasMore.set(false);
      error.set(null);
      loading.set(false);
    },
  };
}

export type ListResource<T> = ReturnType<typeof createListResource<T>>;
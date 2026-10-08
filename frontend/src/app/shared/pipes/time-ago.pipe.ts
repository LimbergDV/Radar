import { Pipe, PipeTransform } from '@angular/core';

/** "hace 3 h", "ayer", "5 mar". Relative para lo reciente, fecha corta para lo viejo. */
@Pipe({ name: 'timeAgo', standalone: true })
export class TimeAgoPipe implements PipeTransform {
  transform(value: string | Date | null | undefined): string {
    if (!value) {
      return '';
    }

    const date = typeof value === 'string' ? new Date(value) : value;
    if (Number.isNaN(date.getTime())) {
      return '';
    }

    const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
    if (seconds < 60) {
      return 'ahora';
    }

    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
      return `hace ${minutes} min`;
    }

    const hours = Math.floor(minutes / 60);
    if (hours < 24) {
      return `hace ${hours} h`;
    }

    const days = Math.floor(hours / 24);
    if (days === 1) {
      return 'ayer';
    }
    if (days < 7) {
      return `hace ${days} días`;
    }

    // Más de una semana: fecha corta, sin año.
    return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' });
  }
}
import { Pipe, PipeTransform } from '@angular/core';

/** 1_200 → "1.2k", 3_400_000 → "3.4M". Para métricas de tarjetas. */
@Pipe({ name: 'compactNumber', standalone: true })
export class CompactNumberPipe implements PipeTransform {
  transform(value: number | null | undefined): string {
    if (value === null || value === undefined || Number.isNaN(value)) {
      return '0';
    }

    const abs = Math.abs(value);
    if (abs < 1000) {
      return String(value);
    }

    const units: [number, string][] = [
      [1_000_000_000, 'B'],
      [1_000_000, 'M'],
      [1_000, 'k'],
    ];

    for (const [threshold, suffix] of units) {
      if (abs >= threshold) {
        const scaled = value / threshold;
        // Una sola cifra decimal, y se quita si es 0 ("1k" no "1.0k").
        const rounded = Math.round(scaled * 10) / 10;
        return `${rounded % 1 === 0 ? rounded.toFixed(0) : rounded.toFixed(1)}${suffix}`;
      }
    }

    return String(value);
  }
}

/** 3725 → "1:02:05". Duraciones de video. */
@Pipe({ name: 'duration', standalone: true })
export class DurationPipe implements PipeTransform {
  transform(totalSeconds: number | null | undefined): string {
    if (!totalSeconds || totalSeconds <= 0) {
      return '';
    }

    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;

    const pad = (n: number) => String(n).padStart(2, '0');
    return hours > 0 ? `${hours}:${pad(minutes)}:${pad(seconds)}` : `${minutes}:${pad(seconds)}`;
  }
}
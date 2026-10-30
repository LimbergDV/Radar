/**
 * Render de READMEs de GitHub: markdown -> HTML seguro.
 *
 * El backend guarda el markdown crudo y la web lo pintaba dentro de un `<pre>`,
 * así que se veían los `#`, los `**` y los bloques de código tal cual. Aquí se
 * convierte a HTML y se sanea.
 *
 * Dos cosas que no son obvias:
 *
 * 1. **Sanitizar no es opcional.** El README es contenido de terceros y puede
 *    traer `<script>`, `onerror=` o un `href="javascript:..."`. DOMPurify quita
 *    todo eso; `bypassSecurityTrustHtml` solo le dice a Angular que no vuelva a
 *    escaparlo, no lo hace seguro por sí mismo.
 * 2. **Las rutas relativas se rompen.** Un README escribe `assets/banner.png` o
 *    `./images/cover.png` porque en GitHub eso resuelve contra el repo. Servido
 *    desde nuestra web, ese `src` apunta a nuestro dominio y da 404. Se
 *    reescriben a `raw.githubusercontent.com` (imágenes) y a
 *    `github.com/.../blob/...` (enlaces).
 */

import DOMPurify from 'dompurify';
import { Marked } from 'marked';

/** Lo mínimo del repo que hace falta para resolver rutas relativas. */
export interface ReadmeRepo {
  full_name: string;
  default_branch: string;
  html_url: string;
}

const RAW_HOST = 'https://raw.githubusercontent.com';

const marked = new Marked({ gfm: true, breaks: false });

/** Convierte markdown de README en HTML saneado y con las rutas resueltas. */
export function renderReadme(markdown: string, repo: ReadmeRepo): string {
  const html = marked.parse(markdown ?? '', { async: false }) as string;

  // El documento que crea DOMParser está inerte: no ejecuta scripts ni carga
  // imágenes, así que es seguro manipularlo antes de sanear.
  const doc = new DOMParser().parseFromString(html, 'text/html');
  rewriteUrls(doc, repo);

  return DOMPurify.sanitize(doc.body.innerHTML, {
    // `target`/`rel` los añadimos nosotros y DOMPurify los quitaría; `align`,
    // `width` y `height` son los que usan los `<p align="center">` e `<img>`
    // de los README reales.
    ADD_ATTR: ['target', 'rel', 'align', 'width', 'height'],
    FORBID_TAGS: ['style', 'form', 'input', 'iframe'],
  });
}

function rewriteUrls(doc: Document, repo: ReadmeRepo): void {
  const blobBase = `${repo.html_url.replace(/\/$/, '')}/blob/${repo.default_branch || 'main'}`;
  const rawBase = `${RAW_HOST}/${repo.full_name}/${repo.default_branch || 'main'}`;

  for (const img of Array.from(doc.querySelectorAll('img[src]'))) {
    const src = img.getAttribute('src');
    if (src) {
      img.setAttribute('src', resolveUrl(src, rawBase));
    }
  }

  for (const anchor of Array.from(doc.querySelectorAll('a[href]'))) {
    const href = anchor.getAttribute('href');
    if (!href) {
      continue;
    }
    anchor.setAttribute('href', resolveUrl(href, blobBase));

    // Un enlace a otro sitio dentro del README debe abrirse fuera: sacar al
    // usuario de la app sin aviso es peor que un target="_blank".
    if (!href.startsWith('#')) {
      anchor.setAttribute('target', '_blank');
      anchor.setAttribute('rel', 'noopener noreferrer');
    }
  }
}

/**
 * Deja intactas las URLs absolutas y resuelve las relativas contra `base`.
 *
 * Los anclas (`#instalacion`) se quedan igual: apuntan a esta misma página.
 */
export function resolveUrl(raw: string, base: string): string {
  const url = raw.trim();
  if (!url) {
    return url;
  }
  if (url.startsWith('#') || /^(https?:)?\/\//i.test(url) || /^(mailto|tel|data):/i.test(url)) {
    return url;
  }
  return `${base}/${url.replace(/^\.?\//, '')}`;
}

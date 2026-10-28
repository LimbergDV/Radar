/** Papers de Hugging Face (`/api/papers`).
 *
 *  El backend guarda el abstract y el AI summary de HF; el PDF sólo se enlaza.
 *  `id` es el id de arXiv (p. ej. `2610.36082`). */

export interface PaperSummary {
  id: string;
  title: string;
  published_at: string;
  submitted_on_daily_at: string | null;
  upvotes: number;
  comments: number;
  thumbnail_url: string | null;
  organization: string | null;
  authors: string[];
  ai_keywords: string[];
  ai_summary: string;
  github_repo: string | null;
  project_page: string | null;
  arxiv_url: string;
  pdf_url: string;
  hf_url: string;
  source: 'daily' | 'search';
}

export interface PaperDetail extends PaperSummary {
  abstract: string;
  linked_models: string[];
  linked_datasets: string[];
  linked_spaces: string[];
  synced_at: string;
}

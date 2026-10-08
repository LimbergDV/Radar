import {
  Activity,
  ArrowLeft,
  Bookmark,
  Calendar,
  Check,
  ChevronRight,
  CircleAlert,
  Code,
  Database,
  ExternalLink,
  Eye,
  FileText,
  GitFork,
  Github,
  Hash,
  Info,
  LayoutGrid,
  Loader,
  Newspaper,
  RefreshCw,
  Search,
  Settings,
  Star,
  Users,
  X,
  Youtube,
} from 'lucide-angular';

/**
 * Registro central de iconos. La librería trae 1700; aquí sólo se registran los
 * que la app usa, así el bundle no los arrastra.
 *
 * Se registra en `app.config.ts` con `LucideAngularModule.pick()`, y los
 * componentes standalone usan `name="..."` (no `[img]`, que espera el nodo).
 */
export const RADAR_ICONS = {
  Activity,
  ArrowLeft,
  Bookmark,
  Calendar,
  Check,
  ChevronRight,
  CircleAlert,
  Code,
  Database,
  ExternalLink,
  Eye,
  FileText,
  GitFork,
  Github,
  Hash,
  Info,
  LayoutGrid,
  Loader,
  Newspaper,
  RefreshCw,
  Search,
  Settings,
  Star,
  Users,
  X,
  Youtube,
};

/** Nombres válidos, para que el typo no pase a runtime. */
export type RadarIconName = keyof typeof RADAR_ICONS;
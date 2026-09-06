import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";

interface SitemapSection {
  to: string;
  labelKey: string;
  children?: { to: string; label: string }[];
}

const SECTIONS: SitemapSection[] = [
  {
    to: "/",
    labelKey: "nav.home",
    children: [
      { to: "/#build-status", label: "Build status, honestly" },
      { to: "/#the-gap", label: "The problem, explained properly" },
      { to: "/#what-makes-it-different", label: "What makes it different" },
      { to: "/#architecture", label: "System architecture" },
      { to: "/#why-now", label: "Why now" },
      { to: "/#competitive-landscape", label: "Competitive landscape" },
    ],
  },
  { to: "/digital-twin", labelKey: "nav.digitalTwin" },
  {
    to: "/services",
    labelKey: "nav.services",
    children: [
      { to: "/services#graph-fusion-engine", label: "Graph Fusion Engine" },
      { to: "/services#drift-memory-engine", label: "Drift Memory Engine" },
      { to: "/services#nowcast-engine", label: "Nowcast Engine" },
      { to: "/services#data-layer", label: "Data layer" },
      { to: "/services#api-contract", label: "API contract" },
    ],
  },
  {
    to: "/about",
    labelKey: "nav.about",
    children: [{ to: "/about#who-this-is-for", label: "Who this is for" }],
  },
  { to: "/sitemap", labelKey: "nav.sitemap" },
];

export function Sitemap() {
  const { t } = useI18n();

  return (
    <div className="mx-auto max-w-3xl px-6 py-32">
      <p className="font-nav text-xs opacity-60">VARUNA</p>
      <h1 className="font-display mt-3 text-5xl sm:text-6xl">{t("sitemap.title")}</h1>
      <p className="mt-6 max-w-xl opacity-75">{t("sitemap.intro")}</p>

      <ul className="mt-16 space-y-8">
        {SECTIONS.map((section) => (
          <li key={section.to}>
            <Link to={section.to} className="font-display text-2xl transition-opacity hover:opacity-70">
              {t(section.labelKey)}
            </Link>
            {section.children && (
              <ul className="mt-3 ml-1 space-y-2 border-l pl-5" style={{ borderColor: "var(--color-border)" }}>
                {section.children.map((child) => (
                  <li key={child.to}>
                    <Link to={child.to} className="text-sm opacity-70 transition-opacity hover:opacity-100">
                      {child.label}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

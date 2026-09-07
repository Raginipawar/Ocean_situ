import { Link, NavLink } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";
import { AccessibilityBar } from "./AccessibilityBar";

export function Nav() {
  const { t } = useI18n();

  const links = [
    { to: "/", label: t("nav.home") },
    { to: "/digital-twin", label: t("nav.digitalTwin") },
    { to: "/explorer", label: t("nav.explorer") },
    { to: "/services", label: t("nav.services") },
    { to: "/about", label: t("nav.about") },
  ];

  return (
    <header className="glass-bar fixed inset-x-0 top-0 z-50 border-b border-[var(--color-border)] dark:border-black">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-3">
        <NavLink to="/" className="font-display text-2xl tracking-tight">
          VARUNA
        </NavLink>

        <div className="flex flex-wrap items-center gap-5">
          <nav className="flex items-center gap-5">
            {links.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                end={link.to === "/"}
                className={({ isActive }) =>
                  `font-nav text-xs transition-opacity hover:opacity-100 ${isActive ? "opacity-100" : "opacity-60"}`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>

          <span className="hidden h-5 w-px sm:block" style={{ backgroundColor: "var(--color-border)" }} />

          <AccessibilityBar />
        </div>
      </div>

      <div
        className="px-6 py-1.5"
        style={{ backgroundColor: "var(--palette-ambassador-blue)", color: "#ffffff" }}
      >
        <div className="mx-auto flex max-w-7xl justify-end gap-4">
          <Link to="/services#data-layer" className="font-nav text-[10px] opacity-75 transition-opacity hover:opacity-100">
            Data Sources
          </Link>
          <Link to="/services#api-contract" className="font-nav text-[10px] opacity-75 transition-opacity hover:opacity-100">
            API Docs
          </Link>
          <Link to="/sitemap" className="font-nav text-[10px] opacity-75 transition-opacity hover:opacity-100">
            Sitemap
          </Link>
        </div>
      </div>
    </header>
  );
}

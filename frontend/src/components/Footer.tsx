import { Link } from "react-router-dom";
import { useI18n } from "../i18n/I18nProvider";

export function Footer() {
  const { t } = useI18n();

  return (
    <footer className="border-t px-6 py-10" style={{ borderColor: "var(--color-border)" }}>
      <div className="mx-auto flex max-w-7xl flex-col gap-2 text-xs opacity-60 sm:flex-row sm:items-center sm:justify-between">
        <p className="font-nav">{t("footer.tagline")}</p>
        <p className="font-mono-data">{t("footer.ministry")}</p>
        <Link to="/sitemap" className="font-nav transition-opacity hover:opacity-100">
          {t("nav.sitemap")}
        </Link>
      </div>
    </footer>
  );
}

import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useAccessibility } from "../theme/AccessibilityProvider";
import { useI18n } from "../i18n/I18nProvider";
import { LANGUAGES } from "../i18n/translations";

function ContrastIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3a9 9 0 0 1 0 18Z" fill="currentColor" stroke="none" />
    </svg>
  );
}

function SitemapIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="5" cy="12" r="2.2" />
      <circle cx="17" cy="5" r="2.2" />
      <circle cx="17" cy="19" r="2.2" />
      <path d="M7 12h4M11 12l4-5.5M11 12l4 5.5" />
    </svg>
  );
}

function LanguageIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3c2.5 2.6 3.8 5.8 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.8-3.8-9s1.3-6.4 3.8-9Z" />
    </svg>
  );
}

function ShareIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="18" cy="5" r="2.4" />
      <circle cx="6" cy="12" r="2.4" />
      <circle cx="18" cy="19" r="2.4" />
      <path d="M8.2 10.8 15.8 6.2M8.2 13.2l7.6 4.6" />
    </svg>
  );
}

function barButtonClass(extra = "") {
  return `flex h-7 min-w-7 items-center justify-center gap-1 rounded-full px-2 text-xs opacity-75 transition-opacity hover:opacity-100 ${extra}`;
}

/**
 * The INCOIS-style icon cluster (text size, contrast, sitemap, language,
 * share). Rendered inline inside Nav's single header row, not its own bar,
 * so the site has exactly one fixed header.
 */
export function AccessibilityBar() {
  const { fontStepIndex, increaseFont, decreaseFont, highContrast, toggleHighContrast } = useAccessibility();
  const { lang, setLang, t } = useI18n();
  const [langOpen, setLangOpen] = useState(false);
  const [shared, setShared] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setLangOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  async function handleShare() {
    const shareData = { title: "VARUNA", url: window.location.href };
    if (navigator.share) {
      try {
        await navigator.share(shareData);
        return;
      } catch {
        // user cancelled the native share sheet; fall through to clipboard
      }
    }
    try {
      await navigator.clipboard.writeText(window.location.href);
      setShared(true);
      setTimeout(() => setShared(false), 1800);
    } catch {
      // clipboard unavailable; nothing more we can do here
    }
  }

  return (
    <div className="flex items-center gap-0.5 rounded-full border px-1.5 py-1" style={{ borderColor: "var(--color-border)" }}>
      <button
        type="button"
        onClick={decreaseFont}
        disabled={fontStepIndex === 0}
        aria-label={t("a11y.decreaseFont")}
        className={barButtonClass("font-nav disabled:opacity-25")}
      >
        A-
      </button>
      <button
        type="button"
        onClick={increaseFont}
        disabled={fontStepIndex === 4}
        aria-label={t("a11y.increaseFont")}
        className={barButtonClass("font-nav disabled:opacity-25")}
      >
        A+
      </button>

      <span className="mx-0.5 h-4 w-px" style={{ backgroundColor: "var(--color-border)" }} />

      <button
        type="button"
        onClick={toggleHighContrast}
        aria-pressed={highContrast}
        aria-label={t("a11y.contrast")}
        className={barButtonClass(highContrast ? "opacity-100" : "")}
        title={t("a11y.contrast")}
      >
        <ContrastIcon />
      </button>

      <Link to="/sitemap" aria-label={t("nav.sitemap")} title={t("nav.sitemap")} className={barButtonClass()}>
        <SitemapIcon />
      </Link>

      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setLangOpen((v) => !v)}
          aria-label={t("a11y.language")}
          aria-expanded={langOpen}
          title={t("a11y.language")}
          className={barButtonClass()}
        >
          <LanguageIcon />
        </button>
        {langOpen && (
          <div className="glass-bar absolute right-0 top-9 z-10 min-w-32 rounded-xl p-1.5">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                onClick={() => {
                  setLang(l.code);
                  setLangOpen(false);
                }}
                className="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs opacity-80 transition-opacity hover:opacity-100"
                style={lang === l.code ? { backgroundColor: "var(--color-accent)", color: "var(--color-bg)", opacity: 1 } : undefined}
              >
                {l.nativeLabel}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={handleShare}
        aria-label={t("a11y.share")}
        title={shared ? t("a11y.shareCopied") : t("a11y.share")}
        className={barButtonClass()}
      >
        <ShareIcon />
      </button>
    </div>
  );
}

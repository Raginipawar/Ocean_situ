import { NavLink } from "react-router-dom";
import { useTheme } from "../theme/ThemeProvider";

const LINKS = [
  { to: "/", label: "Home" },
  { to: "/digital-twin", label: "Digital Twin" },
  { to: "/services", label: "Services" },
  { to: "/about", label: "About" },
];

export function Nav() {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b" style={{ borderColor: "var(--color-border)", backgroundColor: "color-mix(in oklab, var(--color-bg) 88%, transparent)", backdropFilter: "blur(10px)" }}>
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <NavLink to="/" className="font-display text-2xl tracking-tight">
          VARUNA
        </NavLink>

        <nav className="flex items-center gap-7">
          {LINKS.map((link) => (
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
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
            className="font-nav text-xs rounded-full border px-3 py-1.5 opacity-70 transition-opacity hover:opacity-100"
            style={{ borderColor: "var(--color-border)" }}
          >
            {theme === "light" ? "Dark" : "Light"}
          </button>
        </nav>
      </div>
    </header>
  );
}

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const FONT_STEPS = [0.875, 1, 1.125, 1.25, 1.375] as const;
const DEFAULT_STEP_INDEX = 1;

interface AccessibilityContextValue {
  fontStepIndex: number;
  increaseFont: () => void;
  decreaseFont: () => void;
  resetFont: () => void;
  highContrast: boolean;
  toggleHighContrast: () => void;
}

const AccessibilityContext = createContext<AccessibilityContextValue | null>(null);

const FONT_STORAGE_KEY = "varuna-font-step";
const CONTRAST_STORAGE_KEY = "varuna-high-contrast";

function getInitialFontStep(): number {
  if (typeof window === "undefined") return DEFAULT_STEP_INDEX;
  const stored = Number(window.localStorage.getItem(FONT_STORAGE_KEY));
  return Number.isInteger(stored) && stored >= 0 && stored < FONT_STEPS.length ? stored : DEFAULT_STEP_INDEX;
}

function getInitialHighContrast(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(CONTRAST_STORAGE_KEY) === "1";
}

export function AccessibilityProvider({ children }: { children: ReactNode }) {
  const [fontStepIndex, setFontStepIndex] = useState(getInitialFontStep);
  const [highContrast, setHighContrast] = useState(getInitialHighContrast);

  useEffect(() => {
    document.documentElement.style.fontSize = `${FONT_STEPS[fontStepIndex] * 16}px`;
    window.localStorage.setItem(FONT_STORAGE_KEY, String(fontStepIndex));
  }, [fontStepIndex]);

  useEffect(() => {
    document.documentElement.classList.toggle("high-contrast", highContrast);
    window.localStorage.setItem(CONTRAST_STORAGE_KEY, highContrast ? "1" : "0");
  }, [highContrast]);

  const increaseFont = useCallback(() => {
    setFontStepIndex((i) => Math.min(i + 1, FONT_STEPS.length - 1));
  }, []);

  const decreaseFont = useCallback(() => {
    setFontStepIndex((i) => Math.max(i - 1, 0));
  }, []);

  const resetFont = useCallback(() => setFontStepIndex(DEFAULT_STEP_INDEX), []);

  const toggleHighContrast = useCallback(() => setHighContrast((v) => !v), []);

  const value = useMemo(
    () => ({ fontStepIndex, increaseFont, decreaseFont, resetFont, highContrast, toggleHighContrast }),
    [fontStepIndex, increaseFont, decreaseFont, resetFont, highContrast, toggleHighContrast],
  );

  return <AccessibilityContext.Provider value={value}>{children}</AccessibilityContext.Provider>;
}

export function useAccessibility(): AccessibilityContextValue {
  const ctx = useContext(AccessibilityContext);
  if (!ctx) throw new Error("useAccessibility must be used within an AccessibilityProvider");
  return ctx;
}

import { useEffect, useRef, useState, type RefObject } from "react";

/**
 * Tracks whether an element is on-screen, so expensive always-animating
 * effects (WebGL canvases) can be unmounted while scrolled away instead of
 * burning GPU time nobody sees. `once` keeps it true after the first time it
 * becomes visible, for effects too heavy to want mounting/unmounting on
 * every scroll in and out.
 */
export function useInView<T extends HTMLElement>(
  options?: IntersectionObserverInit & { once?: boolean },
): [RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  // Deliberately keyed on options?.once only: callers pass an options object
  // literal, which would otherwise change identity every render and tear
  // down/recreate the observer constantly.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (options?.once) observer.disconnect();
        } else if (!options?.once) {
          setInView(false);
        }
      },
      { rootMargin: "200px", ...options },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [options?.once]);

  return [ref, inView];
}

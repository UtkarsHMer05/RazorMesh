'use client';

import { useEffect, useRef, useState } from 'react';

type FadeInProps = {
  delayMs?: number;
  durationMs?: number;
  className?: string;
  children: React.ReactNode;
  as?: 'div' | 'span' | 'p' | 'section';
};

/**
 * FadeIn (master prompt §5):
 * - opacity 0 → 1 via setTimeout(delay)
 * - inline transitionDuration
 * - cleanup timeout on unmount
 * - prefers-reduced-motion → renders the final state immediately
 */
export function FadeIn({
  delayMs = 0,
  durationMs = 1000,
  className,
  children,
  as = 'div',
}: FadeInProps) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const effectiveDelay = reduced ? 0 : delayMs;
    timerRef.current = setTimeout(() => setVisible(true), effectiveDelay);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [delayMs]);

  const style: React.CSSProperties = {
    opacity: visible ? 1 : 0,
    transition: `opacity ${durationMs}ms cubic-bezier(0.22, 0.61, 0.36, 1)`,
  };

  if (as === 'span') {
    return (
      <span className={className} style={style}>
        {children}
      </span>
    );
  }
  if (as === 'p') {
    return (
      <p className={className} style={style}>
        {children}
      </p>
    );
  }
  if (as === 'section') {
    return (
      <section className={className} style={style}>
        {children}
      </section>
    );
  }
  return (
    <div className={className} style={style}>
      {children}
    </div>
  );
}

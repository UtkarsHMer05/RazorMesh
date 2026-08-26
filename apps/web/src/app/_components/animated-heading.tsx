'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

type AnimatedHeadingProps = {
  text: string; // may contain "\n" line separators
  charDelayMs?: number; // default 30
  initialDelayMs?: number; // default 200
  durationMs?: number; // default 500
  className?: string;
  as?: 'h1' | 'h2' | 'h3';
  letterSpacing?: string;
  id?: string;
};

/**
 * AnimatedHeading (master prompt §5):
 * - split by '\n' into lines, then each line into characters
 * - each character: inline-block, opacity 0→1, translateX(-18px → 0), 500ms
 * - charDelay 30ms; global initial delay 200ms
 * - delay formula: (lineIndex * lineLength * charDelay) + (charIndex * charDelay) + initial
 * - spaces render as \u00A0
 * - prefers-reduced-motion → render final state immediately
 */
export function AnimatedHeading({
  text,
  charDelayMs = 30,
  initialDelayMs = 200,
  durationMs = 500,
  className,
  as = 'h1',
  letterSpacing = '-0.04em',
  id,
}: AnimatedHeadingProps) {
  const lines = useMemo(() => text.split('\n'), [text]);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const reduced =
      typeof window !== 'undefined' &&
      window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const effectiveDelay = reduced ? 0 : initialDelayMs;
    timerRef.current = setTimeout(() => setVisible(true), effectiveDelay);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [initialDelayMs]);

  // Each character's delay depends on its position in the document
  // (line index * line length * charDelay + char index * charDelay) so the
  // visual cadence walks left-to-right, top-to-bottom.
  let acc = 0;
  const charDelays: number[] = [];
  for (const line of lines) {
    for (let i = 0; i < line.length; i++) {
      charDelays.push(acc);
      acc += charDelayMs;
    }
    acc += charDelayMs * line.length; // line break costs an extra line's worth
  }

  const Tag = as;

  return (
    <Tag
      id={id}
      className={className}
      style={{ letterSpacing, margin: 0, fontWeight: 400 }}
      aria-label={text}
    >
      {lines.map((line, lineIndex) => {
        // Global character index so the per-char delay walks
        // left-to-right, top-to-bottom.
        const before = lines
          .slice(0, lineIndex)
          .reduce((n, l) => n + l.length, 0);
        return (
          <span
            key={`l${lineIndex}`}
            style={{ display: 'block' }}
            aria-hidden="true"
          >
            {Array.from(line).map((ch, ci) => {
              const globalIndex = before + ci;
              const delay = charDelays[globalIndex] ?? 0;
              return (
                <Char
                  key={`c${globalIndex}`}
                  char={ch}
                  delay={delay}
                  duration={durationMs}
                  visible={visible}
                />
              );
            })}
          </span>
        );
      })}
    </Tag>
  );
}

function Char({
  char,
  delay,
  duration,
  visible,
}: {
  char: string;
  delay: number;
  duration: number;
  visible: boolean;
}) {
  const [shown, setShown] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!visible) return;
    timerRef.current = setTimeout(() => setShown(true), delay);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [visible, delay]);
  return (
    <span
      style={{
        display: 'inline-block',
        opacity: shown ? 1 : 0,
        transform: shown ? 'translateX(0)' : 'translateX(-18px)',
        transition: `opacity ${duration}ms cubic-bezier(0.22, 0.61, 0.36, 1), transform ${duration}ms cubic-bezier(0.22, 0.61, 0.36, 1)`,
        whiteSpace: 'pre',
      }}
    >
      {char === ' ' ? '\u00A0' : char}
    </span>
  );
}

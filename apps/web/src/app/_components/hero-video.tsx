'use client';

import { useEffect, useRef, useState } from 'react';

const HERO_VIDEO_SRC =
  'https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260403_050628_c4e32401-fab4-4a27-b7a8-6e9291cd5959.mp4';

/**
 * HeroVideo (master prompt §3 + §14 + §18):
 * - absolute inset-0 z-0, object-cover
 * - autoplay / loop / muted / playsInline, no controls
 * - NO overlay, NO gradient, NO dimmer
 * - decorative (aria-hidden, tabIndex -1)
 * - black fallback before the network resolves; black fallback on error
 * - no layout shift: the parent container reserves the viewport height
 */
export function HeroVideo() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;
    const onError = () => setFailed(true);
    el.addEventListener('error', onError);
    return () => el.removeEventListener('error', onError);
  }, []);

  if (failed) {
    // Solid black fallback (per master prompt §3: "Black page background is
    // allowed only as a load/failure fallback").
    return (
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 0,
          background: '#000',
        }}
      />
    );
  }

  return (
    <video
      ref={videoRef}
      aria-hidden="true"
      tabIndex={-1}
      autoPlay
      loop
      muted
      playsInline
      preload="metadata"
      poster=""
      src={HERO_VIDEO_SRC}
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: 0,
        width: '100%',
        height: '100%',
        objectFit: 'cover',
      }}
    />
  );
}

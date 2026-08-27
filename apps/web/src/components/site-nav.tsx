import Link from 'next/link';

export function SiteNav() {
  return (
    <header className="site-nav" role="banner">
      <div className="container site-nav__inner">
        <Link href="/" className="site-nav__brand" aria-label="RazorMesh home">
          <span className="site-nav__logo" aria-hidden="true">
            <span className="dot" />
            <span className="sq" />
            <span className="tri" />
          </span>
          <span>RAZORMESH</span>
        </Link>
        <nav className="site-nav__links" aria-label="Primary">
          <Link href="/">Story</Link>
          <Link href="/#architecture">Architecture</Link>
          <Link href="/protocols">Protocols</Link>
          <Link href="/security-lab">Security</Link>
        </nav>
        <div className="site-nav__actions">
          <Link href="/buyer" className="site-nav__login">Log in</Link>
          <Link href="/buyer" className="site-nav__cta" data-testid="nav-cta">
            Get Started
            <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    </header>
  );
}

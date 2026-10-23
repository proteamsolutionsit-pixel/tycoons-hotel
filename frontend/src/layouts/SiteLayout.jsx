/* Shell shared by every public page: skip link, header, mobile menu,
   <main>, footer, sticky booking bar and the gallery lightbox. */
import { useCallback, useLayoutEffect, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigationType } from 'react-router-dom';
import BookSticky from '../components/BookSticky';
import Footer from '../components/Footer';
import Header from '../components/Header';
import { LightboxProvider } from '../components/Lightbox';
import MobileMenu from '../components/MobileMenu';
import { reduceMotion } from '../motion/motion';

const TITLES = {
  '/': 'The Tycoons Hotel — Business Hotel & Wellness, Bengaluru',
  '/rooms': 'Rooms & Suites — The Tycoons Hotel',
  '/dining': 'Fishy Tales — The Tycoons Hotel',
  '/wellness': 'Kai Wellness Spa — The Tycoons Hotel',
  '/meetings': 'Business Lounge — The Tycoons Hotel',
  '/gallery': 'Gallery — The Tycoons Hotel',
  '/careers': 'Careers — The Tycoons Hotel',
  '/contact': 'Contact — The Tycoons Hotel',
  '/book': 'Book Your Stay — The Tycoons Hotel',
  '/booking/find': 'Find Your Booking — The Tycoons Hotel',
};

/* Route changes: jump to the top (or to #anchor) and move focus to <main>,
   as the original's hash router did. Same-page anchors scroll smoothly. */
function useScrollManager() {
  const location = useLocation();
  const navType = useNavigationType();
  const lastPath = useRef(null);

  useLayoutEffect(() => {
    const changedPage = lastPath.current !== location.pathname;
    lastPath.current = location.pathname;
    const title = TITLES[location.pathname] || (location.pathname.startsWith('/booking/')
      ? 'Your Booking — The Tycoons Hotel' : null);
    if (title) document.title = title;

    const id = decodeURIComponent(location.hash.replace(/^#/, ''));
    if (id) {
      const raf = requestAnimationFrame(() => {
        const target = document.getElementById(id);
        if (target) target.scrollIntoView({ behavior: changedPage || reduceMotion ? 'instant' : 'smooth' });
      });
      if (!changedPage) return () => cancelAnimationFrame(raf);
      // On a fresh page, sections above the anchor fill in as their data
      // arrives and push it down. Keep it aligned while the layout settles
      // (up to 2s), and stop as soon as the visitor scrolls themselves.
      const main = document.getElementById('main');
      let stopped = false;
      const stop = () => { stopped = true; };
      const realign = () => { if (!stopped) document.getElementById(id)?.scrollIntoView({ behavior: 'instant' }); };
      const ro = 'ResizeObserver' in window ? new ResizeObserver(realign) : null;
      if (ro && main) ro.observe(main);
      const events = ['wheel', 'touchstart', 'keydown', 'pointerdown'];
      events.forEach((e) => window.addEventListener(e, stop, { passive: true, once: true }));
      const t = setTimeout(() => { stop(); ro?.disconnect(); }, 2000);
      return () => {
        cancelAnimationFrame(raf);
        clearTimeout(t);
        ro?.disconnect();
        events.forEach((e) => window.removeEventListener(e, stop));
      };
    }
    if (changedPage && navType !== 'POP') {
      window.scrollTo({ top: 0, behavior: 'instant' });
      document.getElementById('main')?.focus({ preventScroll: true });
    }
    return undefined;
  }, [location.key, location.pathname, location.hash, navType]);
}

export default function SiteLayout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuButton = useRef(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  useScrollManager();

  return (
    <LightboxProvider>
      <a className="skip-link" href="#main">Skip to content</a>
      <Header onOpenMenu={() => setMenuOpen(true)} menuOpen={menuOpen} menuButtonRef={menuButton} />
      <MobileMenu open={menuOpen} onClose={closeMenu} returnFocusRef={menuButton} />
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
      <Footer />
      <BookSticky />
    </LightboxProvider>
  );
}

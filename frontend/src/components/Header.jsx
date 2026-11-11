/* Fixed header: transparent over a photo hero, solid + compact after
   scrolling 60px. Pages without a photo hero start solid. */
import { useLayoutEffect, useRef } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { useContact } from '../context/SiteContext';
import { CalendarIcon, MenuIcon } from './Icons';

export default function Header({ onOpenMenu, menuOpen, menuButtonRef }) {
  const ref = useRef(null);
  const { pathname } = useLocation();
  const c = useContact();

  useLayoutEffect(() => {
    const header = ref.current;
    if (!header) return undefined;
    header.classList.remove('is-solid', 'is-compact');
    const overPhoto = !!document.querySelector('#main .hero, #main .page-hero');
    if (!overPhoto) header.classList.add('is-solid');
    let ticking = false;
    const update = () => {
      const scrolled = window.scrollY > 60;
      header.classList.toggle('is-compact', scrolled);
      if (overPhoto) header.classList.toggle('is-solid', scrolled);
      ticking = false;
    };
    const onScroll = () => { if (!ticking) { requestAnimationFrame(update); ticking = true; } };
    window.addEventListener('scroll', onScroll, { passive: true });
    update();
    return () => window.removeEventListener('scroll', onScroll);
  }, [pathname]);

  const nav = (to, label) => <NavLink className="u-draw" to={to}>{label}</NavLink>;

  return (
    <header className="site-header" id="top" ref={ref}>
      <div className="site-header__bg" aria-hidden="true" />
      <div className="utility wrap">
        <span className="utility__address" title={`${c.street}${c.street && c.city ? ', ' : ''}${c.city}`}>{c.street}{c.street && c.city ? ', ' : ''}{c.city}</span>
        <div className="utility__links">
          {c.phone && <a className="u-draw" href={c.tel}>{c.phone}</a>}
          {c.email && <a className="u-draw" href={c.mailto}>{c.email}</a>}
        </div>
      </div>
      <nav className="nav wrap" aria-label="Main">
        <button className="icon-btn nav__mobile" type="button" aria-label="Open menu" aria-expanded={menuOpen}
          aria-controls="menu" onClick={onOpenMenu} ref={menuButtonRef}>
          <MenuIcon />
        </button>
        <div className="nav__group">
          {nav('/rooms', 'Stay')}
          {nav('/dining', 'Dining')}
          {nav('/wellness', 'Wellness')}
          {nav('/meetings', 'Lounge')}
        </div>
        <Link className="brand" to="/" aria-label="The Tycoons Hotel, home">
          <img className="brand__dark" src="/assets/logo/logo-on-dark.png" alt="" width="361" height="208" />
          <img className="brand__light" src="/assets/logo/logo-on-light.png" alt="" width="312" height="189" />
          <img className="brand__emblem" src="/assets/logo/emblem-on-light.png" alt="" width="111" height="112" />
        </Link>
        <div className="nav__group nav__group--end">
          {nav('/gallery', 'Gallery')}
          {nav('/careers', 'Careers')}
          {nav('/contact', 'Contact')}
          <Link className="btn btn--gold" to="/rooms#book">Check Rates</Link>
        </div>
        <Link className="icon-btn nav__mobile" to="/rooms#book" aria-label="Book a stay">
          <CalendarIcon />
        </Link>
      </nav>
    </header>
  );
}

/* Full-screen mobile menu with focus trap, Escape to close, and automatic
   close when the viewport grows past the mobile breakpoint. */
import { useEffect, useRef } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useContact } from '../context/SiteContext';
import { CloseIcon } from './Icons';

const LINKS = [['/rooms', 'Stay'], ['/dining', 'Dining'], ['/wellness', 'Wellness'], ['/meetings', 'Lounge'],
  ['/gallery', 'Gallery'], ['/careers', 'Careers'], ['/contact', 'Contact']];

export default function MobileMenu({ open, onClose, returnFocusRef }) {
  const panel = useRef(null);
  const c = useContact();

  useEffect(() => {
    if (!open) return undefined;
    const root = document.documentElement;
    const lastFocus = document.activeElement;
    root.style.overflow = 'hidden';
    const focusables = () => Array.from(panel.current.querySelectorAll('a[href], button:not([disabled])'));
    const t = setTimeout(() => focusables()[0]?.focus(), 50);
    const onKey = (e) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key !== 'Tab') return;
      const f = focusables();
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKey);
    const mq = window.matchMedia('(min-width: 1080px)');
    const onWide = (m) => { if (m.matches) onClose(); };
    mq.addEventListener('change', onWide);
    return () => {
      clearTimeout(t);
      root.style.overflow = '';
      document.removeEventListener('keydown', onKey);
      mq.removeEventListener('change', onWide);
      (returnFocusRef?.current || lastFocus)?.focus?.();
    };
  }, [open, onClose, returnFocusRef]);

  return (
    // Closed, the panel is visibility:hidden (site.css), which already removes
    // it from the tab order and the accessibility tree.
    <div className={'menu' + (open ? ' is-open' : '')} id="menu" role="dialog" aria-modal="true" aria-label="Menu"
      ref={panel}>
      <div className="menu__top">
        <span />
        <button className="icon-btn" type="button" aria-label="Close menu" onClick={onClose}><CloseIcon /></button>
      </div>
      <img className="menu__logo" src="/assets/logo/logo-on-dark.png" alt="The Tycoons Hotel" width="361" height="208" />
      <ul className="menu__list">
        {LINKS.map(([to, label]) => (
          <li key={to}><NavLink to={to} onClick={onClose}>{label}</NavLink></li>
        ))}
      </ul>
      <div className="menu__foot">
        <span>{c.street}{c.street && c.city ? ', ' : ''}{c.city}</span>
        <a href={c.tel}>{c.phone}</a>
        <a href={c.mailto}>{c.email}</a>
        <Link className="btn btn--gold" to="/rooms#book" onClick={onClose}>Check Rates</Link>
      </div>
    </div>
  );
}

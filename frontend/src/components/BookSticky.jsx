/* Phones: a "Book your stay" bar appears once the booking form has
   scrolled away, and hides again over the footer. */
import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function BookSticky() {
  const { pathname } = useLocation();
  const [show, setShow] = useState(false);
  const linkRef = useRef(null);

  useEffect(() => {
    setShow(false);
    const form = document.getElementById('book');
    const footer = document.querySelector('.site-footer');
    if (!form || !('IntersectionObserver' in window)) return undefined;
    let formVisible = true;
    let footerVisible = false;
    const update = () => {
      const pastForm = form.getBoundingClientRect().bottom < 0;
      setShow(pastForm && !formVisible && !footerVisible);
    };
    const io1 = new IntersectionObserver((entries) => { formVisible = entries[0].isIntersecting; update(); });
    io1.observe(form);
    const io2 = footer ? new IntersectionObserver((entries) => { footerVisible = entries[0].isIntersecting; update(); }) : null;
    if (io2) io2.observe(footer);
    window.addEventListener('scroll', update, { passive: true });
    return () => { io1.disconnect(); io2?.disconnect(); window.removeEventListener('scroll', update); };
  }, [pathname]);

  return (
    <div className={'book-sticky' + (show ? ' is-visible' : '')} aria-hidden={!show}>
      <Link className="btn" to={pathname === '/' ? '/#book' : '/rooms#book'} tabIndex={show ? 0 : -1} ref={linkRef}>
        Book your stay
      </Link>
    </div>
  );
}

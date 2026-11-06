/* Homepage rooms carousel: native swipe, mouse drag with snap, prev/next
   buttons, a progress rule, and a "Drag" label that follows the mouse. */
import { useEffect, useLayoutEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { animate, finePointer, gsap, reduceMotion } from '../../motion/motion';
import { NextIcon, PrevIcon } from '../Icons';
import { SplitText } from '../SplitText';

export default function RoomsCarousel({ rooms }) {
  const section = useRef(null);
  const track = useRef(null);
  const prev = useRef(null);
  const next = useRef(null);
  const bar = useRef(null);
  const label = useRef(null);
  const moved = useRef(false);

  // Height of the hidden details, so the title rises by exactly that much
  useLayoutEffect(() => {
    const measure = () => track.current?.querySelectorAll('.room').forEach((c) => {
      const more = c.querySelector('.room__more');
      if (more) c.style.setProperty('--more-h', more.offsetHeight + 12 + 'px');
    });
    measure();
    window.addEventListener('resize', measure);
    document.fonts?.ready.then(measure);
    return () => window.removeEventListener('resize', measure);
  }, [rooms]);

  useEffect(() => {
    const t = track.current;
    if (!t) return undefined;
    const update = () => {
      const max = t.scrollWidth - t.clientWidth;
      const visible = t.clientWidth / t.scrollWidth;
      const p = max > 0 ? t.scrollLeft / max : 1;
      if (bar.current) bar.current.style.transform = `scaleX(${(visible + (1 - visible) * p).toFixed(4)})`;
      if (prev.current) prev.current.disabled = t.scrollLeft <= 2;
      if (next.current) next.current.disabled = t.scrollLeft >= max - 2;
    };
    t.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();

    // Mouse drag; touch and trackpads use native scrolling
    let startX = 0;
    let startLeft = 0;
    let down = false;
    const onDown = (e) => {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      down = true; moved.current = false;
      startX = e.clientX; startLeft = t.scrollLeft;
    };
    const onMove = (e) => {
      if (!down) return;
      const dx = e.clientX - startX;
      if (!moved.current && Math.abs(dx) > 5) { moved.current = true; t.classList.add('is-dragging'); }
      if (moved.current) t.scrollLeft = startLeft - dx;
    };
    const onUp = () => {
      if (!down) return;
      down = false;
      if (!moved.current) return;
      const left = t.scrollLeft;
      t.classList.remove('is-dragging');
      t.scrollLeft = left;
      setTimeout(() => { moved.current = false; }, 0);
    };
    // A drag must not count as a click on the card link
    const onClick = (e) => { if (moved.current) { e.preventDefault(); e.stopPropagation(); } };
    t.addEventListener('pointerdown', onDown);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    t.addEventListener('click', onClick, true);
    return () => {
      t.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
      t.removeEventListener('pointerdown', onDown);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      t.removeEventListener('click', onClick, true);
    };
  }, [rooms]);

  // "Drag" cursor label (mouse only)
  useEffect(() => {
    const t = track.current;
    const l = label.current;
    if (!animate || !finePointer || !t || !l) return undefined;
    const followX = gsap.quickTo(l, 'x', { duration: 0.45, ease: 'power3' });
    const followY = gsap.quickTo(l, 'y', { duration: 0.45, ease: 'power3' });
    const enter = (e) => {
      gsap.set(l, { x: e.clientX, y: e.clientY });
      gsap.to(l, { scale: 1, opacity: 1, duration: 0.4, ease: 'power3.out', overwrite: 'auto' });
    };
    const move = (e) => { followX(e.clientX); followY(e.clientY); };
    const leave = () => gsap.to(l, { scale: 0, opacity: 0, duration: 0.3, ease: 'power3.in', overwrite: 'auto' });
    const press = () => gsap.to(l, { scale: 0.8, duration: 0.25 });
    const release = () => { if (t.matches(':hover')) gsap.to(l, { scale: 1, duration: 0.25 }); };
    t.addEventListener('pointerenter', enter);
    t.addEventListener('pointermove', move);
    t.addEventListener('pointerleave', leave);
    t.addEventListener('pointerdown', press);
    window.addEventListener('pointerup', release);
    return () => {
      t.removeEventListener('pointerenter', enter);
      t.removeEventListener('pointermove', move);
      t.removeEventListener('pointerleave', leave);
      t.removeEventListener('pointerdown', press);
      window.removeEventListener('pointerup', release);
      gsap.killTweensOf(l);
    };
  }, [rooms]);

  const step = (dir) => {
    const t = track.current;
    const card = t?.querySelector('.room');
    if (!card) return;
    const gap = parseFloat(getComputedStyle(t).columnGap) || 0;
    t.scrollBy({ left: dir * (card.offsetWidth + gap), behavior: reduceMotion ? 'auto' : 'smooth' });
  };

  return (
    <section className="section bg-alt rooms" id="stay" aria-labelledby="rooms-title" ref={section}>
      <div className="wrap section-head">
        <div className="stack stack--tight" data-reveal-children="">
          <p className="kicker">Accommodations</p>
          <SplitText as="h2" id="rooms-title" text="Rooms & Suites" />
        </div>
        <div className="section-head__aside" data-reveal="">
          <Link className="link" to="/rooms">View all rooms</Link>
          <div className="carousel__controls">
            <button className="icon-btn carousel__btn" type="button" aria-label="Previous room" ref={prev} onClick={() => step(-1)}><PrevIcon /></button>
            <button className="icon-btn carousel__btn" type="button" aria-label="Next room" ref={next} onClick={() => step(1)}><NextIcon /></button>
          </div>
        </div>
      </div>

      <ul className="carousel" tabIndex={0} aria-label="Rooms and suites, scroll horizontally" data-carousel="" ref={track}>
        {rooms.map((r) => (
          <li className={'room' + (r.is_signature ? ' room--suite' : '')} key={r.slug}>
            <Link className="room__link" to={`/?room=${encodeURIComponent(r.slug)}#book`}>
              <img src={r.image_url} alt={r.image_alt || r.name} loading="lazy" draggable="false" />
              <div className="room__info">
                <div className="room__head">
                  <h3>{r.name}</h3>
                  {r.inclusions && <p className="room__meta">{r.inclusions}</p>}
                </div>
                <div className="room__more">
                  <p>{r.summary}</p>
                  <span className="room__cta">Check rates</span>
                </div>
              </div>
            </Link>
          </li>
        ))}
      </ul>
      <div className="drag-cursor" aria-hidden="true" ref={label}>Drag</div>
      <div className="wrap">
        <div className="carousel__progress" aria-hidden="true"><span ref={bar} /></div>
      </div>
    </section>
  );
}

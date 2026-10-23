/* Homepage hero: Ken Burns slideshow with crossfades, progress dots and a
   pause button; pauses itself while off screen. Ported from heroMedia(). */
import { useLayoutEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { animate, gsap } from '../../motion/motion';
import { PauseIcon, PlayIcon } from '../Icons';
import { SplitText } from '../SplitText';

const SLIDES = [
  { src: '/assets/img/hero-city.jpg', alt: 'City skyline at dusk', w: 1920, h: 1280 },
  { src: '/assets/img/gal-suite.jpg', alt: '', w: 900, h: 600 },
  { src: '/assets/img/dining-dish.jpg', alt: '', w: 1200, h: 800 },
  { src: '/assets/img/spa.jpg', alt: '', w: 800, h: 546 },
];
const HOLD = 7;   // seconds each image is on screen
const FADE = 2.2; // crossfade

export default function HeroSlideshow() {
  const heroRef = useRef(null);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const control = useRef({ setPaused: () => {} });
  // frames after the first load once the page has finished loading
  const [loadRest, setLoadRest] = useState(false);

  useLayoutEffect(() => {
    const onLoad = () => setLoadRest(true);
    if (document.readyState === 'complete') setLoadRest(true);
    else window.addEventListener('load', onLoad);
    return () => window.removeEventListener('load', onLoad);
  }, []);

  useLayoutEffect(() => {
    const hero = heroRef.current;
    if (!animate || !hero) return undefined;
    const slides = Array.from(hero.querySelectorAll('.hero__slide'));
    const dots = Array.from(hero.querySelectorAll('.hero__dot'));
    let current = -1;
    let running = [];
    let timer = null;
    const ctx = gsap.context(() => {}, hero);

    const dotTween = (dot) => {
      let bar = dot.firstElementChild;
      if (!bar) {
        bar = document.createElement('span');
        bar.style.cssText = 'position:absolute;inset:0;background:currentColor;transform-origin:0 50%;transform:scaleX(0)';
        dot.style.color = 'var(--c-on-brand)';
        dot.appendChild(bar);
      }
      if (dot === dots[0]) dots.forEach((d) => { if (d.firstElementChild) gsap.set(d.firstElementChild, { scaleX: 0 }); });
      return gsap.fromTo(bar, { scaleX: 0 }, { scaleX: 1, duration: HOLD, ease: 'none' });
    };

    const go = (i) => ctx.add(() => {
      const prevSlide = slides[current];
      current = i % slides.length;
      const slide = slides[current];
      const pic = slide.querySelector('img');
      const tl = gsap.timeline({ onComplete: () => { running = running.filter((t) => t !== tl); } });
      const zoomIn = current % 2 === 0;
      gsap.set(slide, { zIndex: 2 });
      if (prevSlide) gsap.set(prevSlide, { zIndex: 1 });
      tl.fromTo(slide, { opacity: prevSlide ? 0 : 1 }, { opacity: 1, duration: prevSlide ? FADE : 0, ease: 'sine.inOut' }, 0);
      tl.fromTo(pic, { scale: zoomIn ? 1 : 1.12, xPercent: zoomIn ? 0 : 1.5 },
        { scale: zoomIn ? 1.12 : 1, xPercent: zoomIn ? -1.5 : 0, duration: HOLD + FADE * 2, ease: 'none' }, 0);
      if (prevSlide) tl.to(prevSlide, { opacity: 0, duration: FADE, ease: 'sine.inOut' }, 0.2);
      const dot = dots[current];
      if (dot) tl.add(dotTween(dot), 0);
      running.push(tl);
      timer = gsap.delayedCall(HOLD, () => go(current + 1));
      slides.forEach((s) => s.classList.remove('is-active'));
      slide.classList.add('is-active');
    });

    const setRunPaused = (p) => {
      running.forEach((t) => (p ? t.pause() : t.resume()));
      if (timer) (p ? timer.pause() : timer.resume());
    };
    control.current.setPaused = setRunPaused;

    // Don't spend frames on the slideshow while it is off screen
    const io = new IntersectionObserver((entries) => {
      if (pausedRef.current) return;
      setRunPaused(!entries[0].isIntersecting);
    });
    io.observe(hero);
    go(0);

    return () => {
      io.disconnect();
      if (timer) timer.kill();
      running.forEach((t) => t.kill());
      ctx.revert();
      dots.forEach((d) => { d.textContent = ''; d.style.color = ''; });
    };
  }, []);

  const togglePause = () => {
    const p = !paused;
    pausedRef.current = p;
    setPaused(p);
    control.current.setPaused(p);
  };

  return (
    <section className="hero" aria-label="Welcome" ref={heroRef}>
      <div className="hero__media">
        {/* Hero film slot: add <source src="/assets/video/hero.mp4" type="video/mp4"> to replace the slideshow. */}
        <video className="hero__video" muted playsInline loop preload="none" poster="/assets/img/hero-city.jpg" aria-hidden="true" />
        {SLIDES.map((s, i) => (
          <figure className={'hero__slide' + (i === 0 ? ' is-active' : '')} key={s.src}>
            <img src={i === 0 || loadRest ? s.src : undefined} alt={s.alt} width={s.w} height={s.h}
              fetchpriority={i === 0 ? 'high' : undefined} decoding={i === 0 ? undefined : 'async'} />
          </figure>
        ))}
      </div>
      <div className="hero__shade" aria-hidden="true" />

      <div className="hero__content">
        <p className="kicker" data-hero-fade="">Business Hotel &amp; Wellness · Bengaluru</p>
        <SplitText as="h1" mode="lines" text="Crafted for comfort, connection, and effortless indulgence." />
        <p className="hero__lede" data-hero-fade="">Refined rooms, intuitive service, coastal dining and restorative wellness — under one roof in the heart of the city.</p>
        <Link className="btn btn--ghost" to="/#stay" data-hero-fade="">Explore Rooms</Link>
      </div>

      <div className="hero__foot" data-hero-fade="">
        <div className="hero__progress">
          <button className="icon-btn hero__pause" type="button" aria-pressed={paused}
            aria-label={paused ? 'Play slideshow' : 'Pause slideshow'} onClick={togglePause}>
            <PauseIcon /><PlayIcon />
          </button>
          <div className="hero__dots" aria-hidden="true">
            {SLIDES.map((s) => <span className="hero__dot" key={s.src} />)}
          </div>
        </div>
        <Link className="scroll-cue" to="/#vision" aria-label="Scroll to content">
          <span className="scroll-cue__label">Scroll</span>
          <span className="scroll-cue__track" aria-hidden="true" />
        </Link>
      </div>
    </section>
  );
}

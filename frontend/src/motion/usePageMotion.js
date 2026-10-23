/* Scroll-driven motion for a page, ported from the original mountView()
   "withGsap" block. Runs once the page's data has rendered (`ready`) and is
   fully reverted when the page unmounts. Line-split headings, the word
   cascade, the hero slideshow and the carousel's drag cursor live in their
   own components. */
import { useLayoutEffect } from 'react';
import { animate, finePointer, gsap, ScrollTrigger } from './motion';

export function usePageMotion(ready = true) {
  useLayoutEffect(() => {
    if (!animate || !ready) return undefined;
    const root = document.getElementById('main');
    if (!root) return undefined;
    const $$ = (s, c = root) => Array.from(c.querySelectorAll(s));
    const mm = gsap.matchMedia();
    const cleanups = [];

    const ctx = gsap.context(() => {
      /* DINING + WELLNESS: clip-path reveal + parallax */
      $$('[data-clip]').forEach((frame) => {
        gsap.fromTo(frame, { clipPath: 'inset(100% 0% 0% 0%)' }, {
          clipPath: 'inset(0% 0% 0% 0%)', duration: 1.6, ease: 'power3.inOut',
          scrollTrigger: { trigger: frame, start: 'top 82%', once: true },
        });
      });
      $$('[data-parallax]').forEach((img) => {
        gsap.fromTo(img, { yPercent: -7 }, {
          yPercent: 7, ease: 'none',
          scrollTrigger: { trigger: img.parentElement, start: 'top bottom', end: 'bottom top', scrub: true },
        });
      });

      /* HERO depth: headline lifts away, photo sinks; photo drifts with the mouse */
      const hero = root.querySelector('.hero');
      if (hero) {
        const heroPhoto = hero.querySelector('.hero__media');
        const heroCopy = hero.querySelector('.hero__content');
        gsap.to(heroCopy, {
          yPercent: -14, opacity: 0, ease: 'none',
          scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom 15%', scrub: true },
        });
        gsap.to(heroPhoto, {
          yPercent: 14, ease: 'none',
          scrollTrigger: { trigger: hero, start: 'top top', end: 'bottom top', scrub: true },
        });
        if (finePointer) {
          gsap.set(heroPhoto, { scale: 1.05 });
          const driftX = gsap.quickTo(heroPhoto, 'x', { duration: 1.8, ease: 'power3' });
          const driftY = gsap.quickTo(heroPhoto, 'y', { duration: 1.8, ease: 'power3' });
          const onMove = (e) => {
            driftX((e.clientX / window.innerWidth - 0.5) * -28);
            driftY((e.clientY / window.innerHeight - 0.5) * -18);
          };
          hero.addEventListener('pointermove', onMove);
          cleanups.push(() => hero.removeEventListener('pointermove', onMove));
        }
      }

      /* SUPPORTING COPY: kicker, text and buttons cascade in under a heading */
      $$('[data-reveal-children]').forEach((group) => {
        const kids = Array.from(group.children).filter((k) => !k.hasAttribute('data-split'));
        gsap.to(kids, {
          opacity: 1, y: 0, duration: 1.1, ease: 'expo.out', stagger: 0.09, delay: 0.15,
          scrollTrigger: { trigger: group, start: 'top 85%', once: true },
        });
      });

      /* ROOMS: cards glide in from the right */
      $$('[data-carousel]').forEach((track) => {
        gsap.from($$('.room', track), {
          x: 120, opacity: 0, duration: 1.4, ease: 'expo.out', stagger: 0.1,
          scrollTrigger: { trigger: track, start: 'top 85%', once: true },
        });
      });

      /* NUMBERS: gold rules draw in above each figure */
      $$('[data-draw]').forEach((el) => {
        ScrollTrigger.create({ trigger: el, start: 'top 88%', once: true, onEnter: () => el.classList.add('is-drawn') });
      });

      /* NUMBERS: count up once */
      $$('[data-count]').forEach((el) => {
        const end = parseInt(el.dataset.count, 10);
        const counter = { v: 0 };
        el.textContent = '0';
        gsap.to(counter, {
          v: end, duration: 1.8, ease: 'power2.out',
          onUpdate: () => { el.textContent = Math.round(counter.v); },
          scrollTrigger: { trigger: el, start: 'top 88%', once: true },
        });
      });

      /* SCROLL REVEAL: text blocks and cards fade up once */
      $$('[data-reveal]').forEach((el) => {
        gsap.to(el, { opacity: 1, y: 0, duration: 1.2, ease: 'expo.out',
          scrollTrigger: { trigger: el, start: 'top 88%', once: true } });
      });

      /* Staggered fade-up of lists */
      $$('[data-stagger]').forEach((group) => {
        gsap.to(group.children, { opacity: 1, y: 0, duration: 1.2, ease: 'expo.out', stagger: 0.12,
          scrollTrigger: { trigger: group, start: 'top 85%', once: true } });
      });

      /* GALLERY PAGE: tiles fade up in batches (the first six show at load) */
      $$('[data-batch]').forEach((group) => {
        ScrollTrigger.batch(Array.from(group.children).slice(6), {
          start: 'top 92%', once: true,
          onEnter: (els) => gsap.to(els, { opacity: 1, y: 0, duration: 1.1, ease: 'expo.out', stagger: 0.08 }),
        });
      });
    }, root);

    /* HOME GALLERY: photos drift at different speeds (wide screens) */
    mm.add('(min-width: 900px)', () => {
      $$('.gallery__grid > li').forEach((li, i) => {
        gsap.fromTo(li.querySelector('.gallery__item'), { y: i % 2 ? 50 : 15 }, {
          y: i % 2 ? -50 : -15, ease: 'none',
          scrollTrigger: { trigger: li.parentElement, start: 'top bottom', end: 'bottom top', scrub: true },
        });
      });
    });

    const refresh = () => ScrollTrigger.refresh();
    window.addEventListener('load', refresh);
    const raf = requestAnimationFrame(refresh);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('load', refresh);
      cleanups.forEach((fn) => fn());
      mm.revert();
      ctx.revert();
    };
  }, [ready]);
}

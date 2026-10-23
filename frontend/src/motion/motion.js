/* Motion flags shared by every animated component. Mirrors the original:
   html.motion is set in index.html before paint; html.has-gsap is added
   here because GSAP is bundled (always present) unless motion is reduced. */
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

const mm = (q) => (typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(q).matches : false);

export const reduceMotion = mm('(prefers-reduced-motion: reduce)');
export const finePointer = mm('(hover: hover) and (pointer: fine)');
export const animate = !reduceMotion && typeof window !== 'undefined' && !!window.matchMedia;

if (animate) document.documentElement.classList.add('has-gsap');

export { gsap, ScrollTrigger };

/** Resolves once the display face is available, like the original's
    document.fonts.load(...) with a 600ms fallback. */
export function whenDisplayFont(timeout = 600) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    if (document.fonts && document.fonts.load) {
      document.fonts.load('400 1em "Cormorant Garamond"').then(finish, finish);
      setTimeout(finish, timeout);
    } else finish();
  });
}

export function whenFontsReady() {
  return document.fonts && document.fonts.ready ? document.fonts.ready.then(() => undefined, () => undefined)
    : Promise.resolve();
}

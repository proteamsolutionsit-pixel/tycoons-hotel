/* Line-split headlines, ported from the original splitLines():
   - mode "lines" (data-lines): the page's H1. Splits once the display font
     is in (600ms fallback) and rises line by line on CSS keyframes.
   - mode "split" (data-split): section headings. Split after all fonts are
     ready, then rise with GSAP when scrolled into view.
   Screen readers get the whole sentence via aria-label; the visual lines
   are aria-hidden, exactly as in the original. */
import { Fragment, createElement, useLayoutEffect, useRef, useState } from 'react';
import { animate, gsap, reduceMotion, ScrollTrigger, whenDisplayFont, whenFontsReady } from '../motion/motion';

export function SplitText({ as = 'h2', text, mode = 'split', className, ...rest }) {
  const ref = useRef(null);
  const [phase, setPhase] = useState('plain'); // plain -> measure -> lines
  const [lines, setLines] = useState(null);
  const words = text.trim().split(/\s+/);
  const enabled = mode === 'lines' ? !reduceMotion : animate;

  useLayoutEffect(() => {
    setPhase('plain');
    setLines(null);
    if (!enabled) return undefined;
    let cancelled = false;
    const go = () => { if (!cancelled) setPhase((p) => (p === 'plain' ? 'measure' : p)); };
    (mode === 'lines' ? whenDisplayFont() : whenFontsReady()).then(go);
    return () => { cancelled = true; };
  }, [text, mode, enabled]);

  useLayoutEffect(() => {
    if (phase !== 'measure' || !ref.current) return;
    const out = [];
    let top = null;
    ref.current.querySelectorAll('.w').forEach((w) => {
      if (w.offsetTop !== top) { out.push([]); top = w.offsetTop; }
      out[out.length - 1].push(w.textContent);
    });
    setLines(out.map((l) => l.join(' ')));
    setPhase('lines');
  }, [phase]);

  useLayoutEffect(() => {
    if (phase !== 'lines' || mode !== 'split' || !animate || !ref.current) return undefined;
    const ctx = gsap.context(() => {
      gsap.from(ref.current.querySelectorAll('.line > span'), {
        yPercent: 105, duration: 1.3, ease: 'expo.out', stagger: 0.1,
        scrollTrigger: { trigger: ref.current, start: 'top 88%', once: true },
      });
    });
    ScrollTrigger.refresh();
    return () => ctx.revert();
  }, [phase, mode]);

  const attrs = { ...rest, ref, className: [className, phase === 'lines' ? 'is-split' : ''].filter(Boolean).join(' ') || undefined };
  attrs[mode === 'lines' ? 'data-lines' : 'data-split'] = '';

  let children = text;
  if (phase === 'measure') {
    children = words.map((w, i) => (
      <Fragment key={i}><span className="w">{w}</span>{i < words.length - 1 ? ' ' : null}</Fragment>
    ));
  } else if (phase === 'lines' && lines) {
    attrs['aria-label'] = words.join(' ');
    children = lines.map((l, i) => (
      <span key={i} className="line" aria-hidden="true" style={{ '--i': i }}><span>{l}</span></span>
    ));
  }
  return createElement(as, attrs, children);
}

/* VISION paragraph: writes itself in word by word, once, when it arrives.
   Not scrubbed, so no word is ever left semi-transparent at rest. */
export function ScrubWords({ text, as = 'p', ...rest }) {
  const ref = useRef(null);
  const words = text.trim().split(/\s+/);

  useLayoutEffect(() => {
    if (!animate || !ref.current) return undefined;
    const ctx = gsap.context(() => {
      gsap.from(ref.current.querySelectorAll(':scope > span'), {
        opacity: 0, duration: 0.9, ease: 'power2.out', stagger: 0.035,
        scrollTrigger: { trigger: ref.current, start: 'top 82%', once: true },
      });
    });
    return () => ctx.revert();
  }, [text]);

  if (!animate) return createElement(as, { ...rest, 'data-scrub-words': '' }, text);
  return createElement(as, { ...rest, ref, 'data-scrub-words': '' }, words.map((w, i) => (
    <Fragment key={i}><span>{w}</span>{i < words.length - 1 ? ' ' : null}</Fragment>
  )));
}

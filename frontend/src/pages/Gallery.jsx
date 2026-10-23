import { useState } from 'react';
import { GalleryButton } from '../components/Lightbox';
import { StateMessage } from '../components/Sections';
import { SplitText } from '../components/SplitText';
import { useApi } from '../hooks/useApi';
import { gsap, reduceMotion, ScrollTrigger } from '../motion/motion';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';

const FILTERS = [['all', 'All'], ['rooms', 'Rooms'], ['dining', 'Dining'], ['wellness', 'Wellness'], ['spaces', 'Spaces']];
const LAYOUT_CLASS = { large: 'is-large', wide: 'is-wide' };

export default function Gallery() {
  const gallery = useApi(() => siteApi.gallery(), []);
  const [filter, setFilter] = useState('all');
  const [status, setStatus] = useState('');
  usePageMotion(!gallery.loading);

  const items = gallery.data?.items || [];
  const shown = items.filter((g) => filter === 'all' || g.category === filter);
  const lightboxList = shown.map((g) => ({ src: g.image_url, alt: g.alt }));

  const choose = (cat) => {
    setFilter(cat);
    const count = items.filter((g) => cat === 'all' || g.category === cat).length;
    setStatus(`Showing ${count} photos`);
    requestAnimationFrame(() => {
      const visible = Array.from(document.querySelectorAll('[data-filter-grid] > li:not([hidden])'));
      if (!reduceMotion) {
        gsap.fromTo(visible, { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.8, ease: 'expo.out', stagger: 0.05, overwrite: true });
      }
      ScrollTrigger.refresh();
    });
  };

  return (
    <>
      <section className="page-head" aria-labelledby="page-title">
        <div className="wrap">
          <p className="kicker" data-hero-fade="">Gallery</p>
          <SplitText as="h1" id="page-title" mode="lines" text="A glimpse of the Tycoons" />
          <div className="filters" role="group" aria-label="Filter photos" data-hero-fade="">
            {FILTERS.map(([value, label]) => (
              <button key={value} className="chip" type="button" aria-pressed={filter === value} onClick={() => choose(value)}>{label}</button>
            ))}
          </div>
          <p className="visually-hidden" aria-live="polite">{status}</p>
        </div>
      </section>

      <section className="gallery-page" aria-label="Photos">
        <div className="wrap">
          <StateMessage loading={gallery.loading} error={gallery.error} onRetry={gallery.reload}
            empty={gallery.data && !items.length ? 'Photos are on their way.' : null} />
          {items.length > 0 && (
            <ul className="mosaic" data-filter-grid="" data-batch="">
              {items.map((g, i) => {
                const visibleIndex = shown.indexOf(g);
                return (
                  <li key={g.id} data-cat={g.category} className={LAYOUT_CLASS[g.layout]} hidden={visibleIndex < 0}>
                    <GalleryButton image={g} list={lightboxList} index={Math.max(visibleIndex, 0)}
                      loading={i < 3 ? 'eager' : 'lazy'} fetchPriority={i === 0 ? 'high' : undefined} />
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </>
  );
}

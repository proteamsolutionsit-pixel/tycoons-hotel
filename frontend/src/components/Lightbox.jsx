/* Gallery lightbox: a native <dialog>, stepping through the photos that
   are currently shown in the grid it was opened from. */
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { reduceMotion } from '../motion/motion';
import { CloseIcon, NextIcon, PrevIcon } from './Icons';

const LightboxContext = createContext(() => {});
export const useLightbox = () => useContext(LightboxContext);

export function LightboxProvider({ children }) {
  const dialog = useRef(null);
  const opener = useRef(null);
  const [items, setItems] = useState([]);
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(false);

  const open = useCallback((list, i, el) => {
    opener.current = el || document.activeElement;
    setItems(list);
    setIndex(i);
    const d = dialog.current;
    if (d && !d.open) {
      d.showModal();
      document.documentElement.style.overflow = 'hidden';
      requestAnimationFrame(() => setVisible(true));
    }
  }, []);

  const close = useCallback(() => {
    setVisible(false);
    setTimeout(() => {
      if (dialog.current?.open) dialog.current.close();
      document.documentElement.style.overflow = '';
      opener.current?.focus?.();
    }, reduceMotion ? 0 : 350);
  }, []);

  const step = useCallback((d) => setIndex((i) => (i + d + items.length) % Math.max(items.length, 1)), [items.length]);

  useEffect(() => () => {
    if (dialog.current?.open) dialog.current.close();
    document.documentElement.style.overflow = '';
  }, []);

  const item = items[index];
  return (
    <LightboxContext.Provider value={open}>
      {children}
      <dialog
        className={'lightbox' + (visible ? ' is-visible' : '')}
        aria-label="Gallery image viewer"
        ref={dialog}
        onCancel={(e) => { e.preventDefault(); close(); }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') step(-1);
          if (e.key === 'ArrowRight') step(1);
        }}
        onClick={(e) => {
          const cl = e.target.classList;
          if (cl.contains('lightbox__stage') || cl.contains('lightbox__figure')) close();
        }}
      >
        <div className="lightbox__bar">
          <span>{items.length ? `${index + 1} / ${items.length}` : ''}</span>
          <button className="icon-btn" type="button" aria-label="Close" onClick={close}><CloseIcon /></button>
        </div>
        <div className="lightbox__stage">
          <button className="icon-btn" type="button" aria-label="Previous image" onClick={() => step(-1)}><PrevIcon /></button>
          <figure className="lightbox__figure">{item ? <img src={item.src} alt={item.alt} /> : <img alt="" />}</figure>
          <button className="icon-btn" type="button" aria-label="Next image" onClick={() => step(1)}><NextIcon /></button>
        </div>
        <p className="lightbox__caption">{item?.alt}</p>
      </dialog>
    </LightboxContext.Provider>
  );
}

/** A gallery thumbnail button (same markup as the original). */
export function GalleryButton({ image, list, index, loading = 'lazy', fetchPriority }) {
  const open = useLightbox();
  return (
    <button className="gallery__item" type="button" onClick={(e) => open(list, index, e.currentTarget)}>
      <span className="zoom">
        <img src={image.image_url} alt={image.alt} width={image.width || undefined} height={image.height || undefined}
          loading={loading} fetchpriority={fetchPriority} />
      </span>
    </button>
  );
}

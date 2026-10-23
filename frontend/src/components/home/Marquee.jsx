import { useState } from 'react';
import { PauseIcon, PlayIcon } from '../Icons';

/* Amenities ticker. Items come from the `amenities` site setting. */
export default function Marquee({ items }) {
  const [paused, setPaused] = useState(false);
  const list = (hidden) => (
    <ul className="marquee__list" aria-hidden={hidden || undefined}>
      {items.map((t, i) => <li key={i}>{t}</li>)}
    </ul>
  );
  return (
    <div className={'marquee' + (paused ? ' is-paused' : '')} aria-label="Amenities">
      <div className="marquee__track">{list(false)}{list(true)}</div>
      <button className="icon-btn marquee__pause" type="button" aria-pressed={paused}
        aria-label={paused ? 'Play amenities ticker' : 'Pause amenities ticker'} onClick={() => setPaused((p) => !p)}>
        <PauseIcon small /><PlayIcon small />
      </button>
    </div>
  );
}

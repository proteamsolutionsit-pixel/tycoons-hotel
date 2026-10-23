/* The inline SVG icons from the original markup, unchanged. */
const stroke = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.5, 'aria-hidden': true };

export const MenuIcon = () => <svg {...stroke}><path d="M3 7h18M3 12h18M3 17h18" /></svg>;
export const CloseIcon = () => <svg {...stroke}><path d="M5 5l14 14M19 5L5 19" /></svg>;
export const CalendarIcon = () => <svg {...stroke}><rect x="3" y="5" width="18" height="16" /><path d="M3 10h18M8 3v4M16 3v4" /></svg>;
export const PrevIcon = () => <svg {...stroke}><path d="M15 5l-7 7 7 7" /></svg>;
export const NextIcon = () => <svg {...stroke}><path d="M9 5l7 7-7 7" /></svg>;

export const PauseIcon = ({ small }) => (
  <svg className="icon-pause" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    {small ? (<><rect x="8" y="7" width="2.5" height="10" /><rect x="13.5" y="7" width="2.5" height="10" /></>)
      : (<><rect x="7" y="6" width="3" height="12" /><rect x="14" y="6" width="3" height="12" /></>)}
  </svg>
);
export const PlayIcon = ({ small }) => (
  <svg className="icon-play" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d={small ? 'M9 6.5v11l9-5.5z' : 'M8 5.5v13l11-6.5z'} />
  </svg>
);

/* Guests field for the booking bar: a button that looks like the other
   fields and opens a small panel with - / + steppers for adults and children.
   Limits match the server's (1-6 adults, 0-4 children). */
import { useEffect, useId, useRef, useState } from 'react';

export const LIMITS = { adults: [1, 6], children: [0, 4] };

export function guestSummary(adults, children) {
  const a = `${adults} Adult${adults === 1 ? '' : 's'}`;
  return children ? `${a}, ${children} Child${children === 1 ? '' : 'ren'}` : a;
}

function Stepper({ label, hint, value, min, max, onChange, noun }) {
  return (
    <div className="guest-picker__row">
      <div className="guest-picker__label">
        <span>{label}</span>
        {hint && <small>{hint}</small>}
      </div>
      <div className="guest-picker__stepper" role="group" aria-label={label}>
        <button type="button" className="guest-picker__btn" aria-label={`Remove ${noun}`} disabled={value <= min}
          onClick={() => onChange(Math.max(min, value - 1))}>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10" /></svg>
        </button>
        <output className="guest-picker__count" aria-live="polite">{value}</output>
        <button type="button" className="guest-picker__btn" aria-label={`Add ${noun}`} disabled={value >= max}
          onClick={() => onChange(Math.min(max, value + 1))}>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8h10M8 3v10" /></svg>
        </button>
      </div>
    </div>
  );
}

/** value: { adults, children }; roomMax: largest room capacity, to warn early. */
export default function GuestPicker({ value, onChange, roomMax }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef(null);
  const toggle = useRef(null);
  const id = useId();
  const { adults, children } = value;

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (!wrap.current?.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') { setOpen(false); toggle.current?.focus(); } };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const tooMany = roomMax && (adults > roomMax.adults || children > roomMax.children);

  return (
    <div className="field field--wide guest-picker" ref={wrap}>
      <span id={`${id}-label`}>Guests</span>
      <button type="button" ref={toggle} className="guest-picker__toggle" aria-haspopup="dialog" aria-expanded={open}
        aria-controls={`${id}-panel`} aria-labelledby={`${id}-label ${id}-value`} onClick={() => setOpen((o) => !o)}>
        <span id={`${id}-value`}>{guestSummary(adults, children)}</span>
      </button>
      {open && (
        <div className="guest-picker__panel" id={`${id}-panel`} role="dialog" aria-label="Choose guests">
          <Stepper label="Adults" hint="Age 13+" noun="adult" value={adults} min={LIMITS.adults[0]} max={LIMITS.adults[1]}
            onChange={(n) => onChange({ adults: n, children })} />
          <Stepper label="Children" hint="Age 0–12" noun="child" value={children} min={LIMITS.children[0]} max={LIMITS.children[1]}
            onChange={(n) => onChange({ adults, children: n })} />
          {tooMany && (
            <p className="guest-picker__note">Our rooms sleep up to {guestSummary(roomMax.adults, roomMax.children).toLowerCase()} each, so we’ll show you prices for enough rooms for everyone.</p>
          )}
          <button type="button" className="btn guest-picker__done" onClick={() => { setOpen(false); toggle.current?.focus(); }}>Done</button>
        </div>
      )}
    </div>
  );
}

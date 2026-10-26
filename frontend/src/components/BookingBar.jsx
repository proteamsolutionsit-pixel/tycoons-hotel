/* "Check availability" bar (home, rooms and the booking page). Submitting
   opens /book with the stay in the query string; prices and availability
   are always computed by the server. */
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { siteApi } from '../services/api';
import { addDays, hotelToday } from '../utils/format';
import GuestPicker, { LIMITS } from './GuestPicker';

const clamp = (n, [lo, hi], fallback) => (Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.trunc(n))) : fallback);

/** "2-1" or URL params -> { adults, children } within the server's limits */
export function parseGuests(text, adults, children) {
  const [a, c] = (text || '').split('-').map(Number);
  return {
    adults: clamp(text ? a : Number(adults ?? 1), LIMITS.adults, 1),
    children: clamp(text ? c : Number(children ?? 0), LIMITS.children, 0),
  };
}

let roomsCache = null;

export default function BookingBar({ className = 'booking', motion = true, initial = {}, onSearch }) {
  const navigate = useNavigate();
  const { search } = useLocation();
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const today = hotelToday();
  const [rooms, setRooms] = useState(roomsCache || []);
  const [values, setValues] = useState(() => ({
    checkin: initial.check_in || params.get('check_in') || '',
    checkout: initial.check_out || params.get('check_out') || '',
    guests: parseGuests(initial.guests, params.get('adults'), params.get('children')),
    room: initial.room ?? params.get('room') ?? '',
  }));
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (roomsCache) return;
    siteApi.rooms().then((r) => { roomsCache = r; setRooms(r); }).catch(() => {});
  }, []);

  // A room link elsewhere on the page (?room=...) preselects it here
  useEffect(() => {
    const r = params.get('room');
    if (r !== null) setValues((v) => ({ ...v, room: r }));
  }, [params]);

  // Largest room, so the picker can warn before the search instead of after
  const roomMax = rooms.some((r) => r.max_adults) ? {
    adults: Math.max(...rooms.map((r) => r.max_adults || 0)),
    children: Math.max(...rooms.map((r) => r.max_children || 0)),
  } : null;

  const set = (k) => (e) => {
    const v = e.target.value;
    setValues((s) => {
      const next = { ...s, [k]: v };
      if (k === 'checkin' && v && (!s.checkout || s.checkout <= v)) next.checkout = addDays(v, 1);
      return next;
    });
    setErrors((er) => ({ ...er, [k]: undefined }));
  };

  const submit = (e) => {
    e.preventDefault();
    const er = {};
    if (!values.checkin) er.checkin = 'Choose a check-in date';
    else if (values.checkin < today) er.checkin = 'Choose today or later';
    if (!values.checkout) er.checkout = 'Choose a check-out date';
    else if (values.checkin && values.checkout <= values.checkin) er.checkout = 'Must be after check-in';
    setErrors(er);
    if (Object.keys(er).length) {
      e.currentTarget.querySelector(`[name="${Object.keys(er)[0]}"]`)?.focus();
      return;
    }
    const { adults, children } = values.guests;
    const q = new URLSearchParams({ check_in: values.checkin, check_out: values.checkout, adults: String(adults), children: String(children) });
    if (values.room) q.set('room', values.room);
    if (onSearch) onSearch(Object.fromEntries(q));
    else navigate(`/book?${q.toString()}`);
  };

  const err = (k) => errors[k] && <span className="field-error" id={`book-${k}-err`} role="alert">{errors[k]}</span>;
  const aria = (k) => ({ 'aria-invalid': errors[k] ? true : undefined, 'aria-describedby': errors[k] ? `book-${k}-err` : undefined });

  return (
    <div className={className} data-hero-fade={motion ? '' : undefined}>
      <div className="wrap">
        <form className="booking__form" id="book" aria-label="Check availability" onSubmit={submit} noValidate>
          <label className="field">Check-in
            <input type="date" name="checkin" min={today} value={values.checkin} onChange={set('checkin')} {...aria('checkin')} />
            {err('checkin')}
          </label>
          <label className="field">Check-out
            <input type="date" name="checkout" min={values.checkin ? addDays(values.checkin, 1) : addDays(today, 1)}
              value={values.checkout} onChange={set('checkout')} {...aria('checkout')} />
            {err('checkout')}
          </label>
          <GuestPicker value={values.guests} roomMax={roomMax} onChange={(g) => setValues((s) => ({ ...s, guests: g }))} />
          <label className="field field--wide">Room
            <select name="room" value={values.room} onChange={set('room')}>
              <option value="">Any room</option>
              {rooms.map((r) => <option key={r.slug} value={r.slug}>{r.name}</option>)}
            </select>
          </label>
          <button className="btn" type="submit">Check Availability</button>
        </form>
      </div>
    </div>
  );
}

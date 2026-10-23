/* "Check availability" bar (home, rooms and the booking page). Submitting
   opens /book with the stay in the query string; prices and availability
   are always computed by the server. */
import { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { siteApi } from '../services/api';
import { addDays, hotelToday } from '../utils/format';

// The three options in the original design, as (adults, children)
export const GUEST_OPTIONS = [
  { value: '1-0', label: '1 Adult' },
  { value: '2-0', label: '2 Adults' },
  { value: '2-1', label: '2 Adults, 1 Child' },
];

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
    guests: initial.guests || `${params.get('adults') || 1}-${params.get('children') || 0}`,
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
    const [adults, children] = values.guests.split('-');
    const q = new URLSearchParams({ check_in: values.checkin, check_out: values.checkout, adults, children });
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
          <label className="field field--wide">Guests
            <select name="guests" value={values.guests} onChange={set('guests')}>
              {GUEST_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
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

/* Occupancy calendar: rooms sold per room type per night.
   Encoding: one-hue (navy) sequential ramp, light = few rooms sold, dark =
   full. Every cell also prints "sold/total" (and holds), so colour is never
   the only carrier; text colour per step was contrast-checked (>= 5.5:1). */
import { useState } from 'react';
import { addDays, hotelToday } from '../../utils/format';
import { PageTitle, useAdminList } from '../ui';

const RAMP = ['#FFFFFF', '#E6E8F2', '#C9CDE3', '#9AA0C8', '#5E649E', '#2B3066'];

function step(sold, total) {
  if (!total || sold <= 0) return 0;
  return Math.min(5, 1 + Math.floor((sold / total) * 4.999)); // 1..5 by share sold, 5 = full
}

const dayFmt = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
const label = (iso) => dayFmt.format(new Date(iso + 'T00:00:00Z'));

export function OccupancyGrid({ state }) {
  if (state.error) return <p className="adm-error" role="alert">{state.error.message}</p>;
  if (!state.data) return <div className="adm-skeleton adm-skeleton--block" aria-label="Loading" />;
  const { days, rooms } = state.data;
  return (
    <div className="adm-occ-wrap">
      <table className="adm-occ">
        <caption className="visually-hidden">Rooms sold out of rooms available, per room type and night</caption>
        <thead>
          <tr>
            <th scope="col">Room type</th>
            {days.map((d) => <th scope="col" key={d}>{label(d)}</th>)}
          </tr>
        </thead>
        <tbody>
          {rooms.map((r) => (
            <tr key={r.slug}>
              <th scope="row">{r.name}<small>{r.total_rooms} rooms</small></th>
              {r.booked.map((sold, i) => {
                const s = step(sold, r.total_rooms);
                const held = r.held[i];
                const tip = `${r.name}, ${label(days[i])}: ${sold} of ${r.total_rooms} sold${held ? `, ${held} on hold awaiting payment` : ''}`;
                return (
                  <td key={days[i]} style={{ background: RAMP[s], color: s >= 4 ? '#FFFFFF' : '#1F2326' }}
                    title={tip} aria-label={tip} className={sold >= r.total_rooms && r.total_rooms ? 'is-full' : undefined}>
                    <span className="adm-occ__n">{sold}<span className="adm-occ__of">/{r.total_rooms}</span></span>
                    {held > 0 && <span className="adm-occ__held">+{held} held</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="adm-occ-legend" aria-hidden="true">
        <span>Fewer rooms sold</span>
        {RAMP.map((c) => <span key={c} className="adm-occ-legend__swatch" style={{ background: c }} />)}
        <span>Sold out</span>
      </div>
    </div>
  );
}

export default function Occupancy() {
  const [start, setStart] = useState(hotelToday());
  const [days, setDays] = useState(14);
  const occ = useAdminList('/api/v1/admin/occupancy', { start, days });
  return (
    <>
      <PageTitle title="Occupancy" subtitle="Confirmed stays (and payments under review) per night; unpaid holds shown separately." />
      <div className="adm-toolbar">
        <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" onClick={() => setStart(addDays(start, -days))}>Previous {days} days</button>
        <label className="adm-inline">From <input type="date" className="adm-input" value={start} onChange={(e) => e.target.value && setStart(e.target.value)} /></label>
        <label className="adm-inline">Show
          <select className="adm-input" value={days} onChange={(e) => setDays(Number(e.target.value))}>
            {[7, 14, 31].map((n) => <option key={n} value={n}>{n} nights</option>)}
          </select>
        </label>
        <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" onClick={() => setStart(addDays(start, days))}>Next {days} days</button>
        <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" onClick={() => setStart(hotelToday())}>Today</button>
      </div>
      <section className="adm-panel"><OccupancyGrid state={occ} /></section>
    </>
  );
}

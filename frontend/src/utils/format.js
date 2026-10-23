const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });
const inrExact = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 });

/** 650000 paise -> "₹6,500" (whole rupees shown without decimals). */
export function rupees(paise, { exact = false } = {}) {
  if (paise === null || paise === undefined || Number.isNaN(Number(paise))) return '';
  const value = Number(paise) / 100;
  return exact || !Number.isInteger(value) ? inrExact.format(value) : inr.format(value);
}

/** Today in the hotel's timezone (Asia/Kolkata) as YYYY-MM-DD. */
export function hotelToday(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(now);
  return parts; // en-CA formats as YYYY-MM-DD
}

export function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split('-').map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return dt.toISOString().slice(0, 10);
}

export function nightsBetween(checkIn, checkOut) {
  const a = Date.parse(checkIn + 'T00:00:00Z');
  const b = Date.parse(checkOut + 'T00:00:00Z');
  return Math.round((b - a) / 86400000);
}

/** "2026-11-02" -> "Mon, 2 Nov 2026" */
export function longDate(iso) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC',
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

/** API datetimes are naive UTC; show them in hotel time. */
export function dateTime(iso) {
  if (!iso) return '';
  const dt = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z');
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata',
  }).format(dt);
}

export function timeOnly(iso) {
  if (!iso) return '';
  const dt = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : iso + 'Z');
  return new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', timeZone: 'Asia/Kolkata' }).format(dt);
}

export function plural(n, one, many = one + 's') {
  return `${n} ${n === 1 ? one : many}`;
}

export function guestsLabel(adults, children) {
  return plural(adults, 'adult') + (children ? ', ' + plural(children, 'child', 'children') : '');
}

export function uuid() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  return Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
}

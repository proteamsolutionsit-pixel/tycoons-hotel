/* Remembers which email belongs to a booking reference for this browser tab,
   so the booking page survives a refresh without asking again. */
const KEY = 'tyc_booking_emails';

function read() {
  try { return JSON.parse(sessionStorage.getItem(KEY) || '{}'); } catch { return {}; }
}

export function rememberBookingEmail(reference, email) {
  try {
    const all = read();
    all[reference] = email;
    sessionStorage.setItem(KEY, JSON.stringify(all));
  } catch { /* storage unavailable: the page will ask for the email */ }
}

export function recallBookingEmail(reference) {
  return read()[reference] || '';
}

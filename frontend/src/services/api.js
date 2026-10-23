/* REST client. Every error is normalised to ApiError with the backend's
   {code, message, details[]} so forms can show field-level messages. */

const BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor({ status = 0, code = 'network_error', message, details = null, requestId = null }) {
    super(message || 'Something went wrong. Please try again.');
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  /** {field: message} for form fields. */
  get fieldErrors() {
    const out = {};
    (Array.isArray(this.details) ? this.details : []).forEach((d) => {
      if (d && d.field && !out[d.field]) out[d.field] = d.message;
    });
    return out;
  }
}

function readCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : '';
}

export async function request(path, { method = 'GET', body, query, headers = {}, signal, form } = {}) {
  let url = BASE + path;
  if (query) {
    const qs = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') qs.append(k, v);
    });
    const s = qs.toString();
    if (s) url += (url.includes('?') ? '&' : '?') + s;
  }
  const h = { Accept: 'application/json', ...headers };
  let payload;
  if (form) {
    payload = form; // FormData: the browser sets the multipart boundary
  } else if (body !== undefined) {
    h['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  if (method !== 'GET' && path.startsWith('/api/v1/admin')) {
    const csrf = readCookie('tyc_csrf');
    if (csrf) h['X-CSRF-Token'] = csrf;
  }

  let res;
  try {
    res = await fetch(url, { method, headers: h, body: payload, signal, credentials: 'same-origin' });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError({ message: 'We could not reach the server. Check your connection and try again.' });
  }

  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await res.json().catch(() => null) : null;
  if (!res.ok) {
    const e = (data && data.error) || {};
    throw new ApiError({
      status: res.status,
      code: e.code || 'http_' + res.status,
      message: e.message || (res.status >= 500 ? 'Something went wrong on our side. Please try again.' : 'Request failed.'),
      details: e.details || null,
      requestId: e.request_id || res.headers.get('x-request-id'),
    });
  }
  return data;
}

export const api = {
  get: (path, query, opts) => request(path, { ...opts, query }),
  post: (path, body, opts) => request(path, { ...opts, method: 'POST', body }),
  put: (path, body, opts) => request(path, { ...opts, method: 'PUT', body }),
  patch: (path, body, opts) => request(path, { ...opts, method: 'PATCH', body }),
  del: (path, opts) => request(path, { ...opts, method: 'DELETE' }),
  upload: (path, form, opts) => request(path, { ...opts, method: 'POST', form }),
};

/* Public endpoints */
export const siteApi = {
  site: () => api.get('/api/v1/site'),
  rooms: () => api.get('/api/v1/rooms'),
  treatments: () => api.get('/api/v1/spa/treatments'),
  cards: (section) => api.get('/api/v1/content/cards', { section }),
  gallery: (query) => api.get('/api/v1/gallery', { limit: 100, ...query }),
  openings: () => api.get('/api/v1/careers/openings'),
  availability: (q) => api.get('/api/v1/bookings/availability', q),
  createBooking: (body, idempotencyKey) =>
    api.post('/api/v1/bookings', body, { headers: { 'Idempotency-Key': idempotencyKey } }),
  lookupBooking: (reference, email) => api.post('/api/v1/bookings/lookup', { reference, email }),
  retryPayment: (reference, email) => api.post(`/api/v1/bookings/${encodeURIComponent(reference)}/payment`, { reference, email }),
  verifyPayment: (body) => api.post('/api/v1/payments/verify', body),
  reportPayment: (body) => api.post('/api/v1/payments/report', body),
  tableReservation: (body) => api.post('/api/v1/dining/reservations', body),
  spaAppointment: (body) => api.post('/api/v1/spa/appointments', body),
  businessEnquiry: (body) => api.post('/api/v1/enquiries/business', body),
  contactEnquiry: (body) => api.post('/api/v1/enquiries/contact', body),
  jobApplication: (form) => api.upload('/api/v1/careers/applications', form),
  newsletter: (body) => api.post('/api/v1/newsletter', body),
};

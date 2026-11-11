/* /book - availability, guest details and Razorpay payment.
   Prices shown here are the server's quote; the amount actually charged is
   computed again by the server when the booking is created. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import BookingBar from '../components/BookingBar';
import { Check, Field, FormStatus } from '../components/forms/Fields';
import { rules, useForm } from '../components/forms/useForm';
import { StateMessage } from '../components/Sections';
import { SplitText } from '../components/SplitText';
import { useSite } from '../context/SiteContext';
import { usePageMotion } from '../motion/usePageMotion';
import { ApiError, siteApi } from '../services/api';
import { openCheckout } from '../services/razorpay';
import { guestsLabel, isFilled, longDate, plural, rateBreakdown, rupees, tariffLine, timeOnly, uuid } from '../utils/format';
import { rememberBookingEmail } from './bookingSession';

export default function Book() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const query = useMemo(() => ({
    check_in: params.get('check_in') || '',
    check_out: params.get('check_out') || '',
    adults: Number(params.get('adults') || 1),
    children: Number(params.get('children') || 0),
    room: params.get('room') || '',
  }), [params]);
  const hasStay = !!(query.check_in && query.check_out);

  const [result, setResult] = useState({ loading: hasStay, data: null, error: null });
  const [selected, setSelected] = useState(null);
  const detailsRef = useRef(null);
  usePageMotion(!result.loading);

  useEffect(() => {
    setSelected(null);
    if (!hasStay) { setResult({ loading: false, data: null, error: null }); return undefined; }
    let cancelled = false;
    setResult({ loading: true, data: null, error: null });
    siteApi.availability({ check_in: query.check_in, check_out: query.check_out, adults: query.adults, children: query.children })
      .then((data) => { if (!cancelled) setResult({ loading: false, data, error: null }); })
      .catch((error) => { if (!cancelled) setResult({ loading: false, data: null, error }); });
    return () => { cancelled = true; };
  }, [hasStay, query.check_in, query.check_out, query.adults, query.children]);

  // Preselect the room chosen in the bar, if it is bookable
  useEffect(() => {
    if (!result.data || !query.room) return;
    const q = result.data.rooms.find((r) => r.slug === query.room && r.bookable);
    if (q) setSelected(q);
  }, [result.data, query.room]);

  useEffect(() => {
    if (selected) requestAnimationFrame(() => detailsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }, [selected]);

  // The room chosen in the bar is listed first; the rest keep the server's order
  const rooms = useMemo(() => {
    const list = result.data?.rooms || [];
    if (!query.room) return list;
    return [...list.filter((r) => r.slug === query.room), ...list.filter((r) => r.slug !== query.room)];
  }, [result.data, query.room]);
  const anyBookable = rooms.some((r) => r.bookable);

  return (
    <>
      <section className="page-head" aria-labelledby="page-title">
        <div className="wrap">
          <p className="kicker" data-hero-fade="">Reservations</p>
          <SplitText as="h1" id="page-title" mode="lines" text="Book your stay" />
        </div>
      </section>

      <BookingBar key={params.toString()} className="booking booking--inline" motion={false}
        initial={{ check_in: query.check_in, check_out: query.check_out, guests: `${query.adults}-${query.children}`, room: query.room }}
        onSearch={(q) => setParams(q)} />

      <section className="section book-flow" aria-labelledby="results-title">
        <div className="wrap">
          <div className="section-head">
            <div className="stack stack--tight">
              <p className="kicker">{hasStay ? `${longDate(query.check_in)} – ${longDate(query.check_out)}` : 'Choose your dates'}</p>
              <h2 id="results-title">{hasStay ? 'Available rooms' : 'When would you like to stay?'}</h2>
            </div>
            <Link className="link" to="/booking/find">Find your booking</Link>
          </div>

          {!hasStay && <p className="book-note">Choose check-in and check-out dates above to see rooms and rates.</p>}
          <StateMessage loading={result.loading} error={result.error}
            onRetry={() => setParams(new URLSearchParams(params))}>Checking availability…</StateMessage>
          {result.data && !anyBookable && (
            <p className="state-msg">No rooms are available for {guestsLabel(query.adults, query.children)} on these dates. Try different dates or <Link className="link" to="/contact">contact reservations</Link>.</p>
          )}

          {rooms.length > 0 && (
            <ul className="cards quote-list" data-stagger="">
              {rooms.map((r) => (
                <li className={'card' + (r.is_signature ? ' room--signature' : '')} key={r.slug}
                  aria-current={selected?.slug === r.slug ? 'true' : undefined}>
                  <span className="card__media zoom"><img src={r.image_url} alt={r.image_alt || r.name} loading="lazy" /></span>
                  <div className="card__body">
                    <h3>{r.name}</h3>
                    {r.bookable && r.room_count > 1 && (
                      <p className="quote-rooms">{plural(r.room_count, 'room')} for your party of {guestsLabel(query.adults, query.children).toLowerCase()}</p>
                    )}
                    <p>{r.summary}</p>
                    {[r.size_label, r.bed_label, r.view_label, r.occupancy_label].some(isFilled) && (
                      <ul className="quote-facts">
                        {[r.size_label, r.bed_label, r.view_label, r.occupancy_label].filter(isFilled).map((f, i) => <li key={i}>{f}</li>)}
                      </ul>
                    )}
                    {tariffLine(r.nightly_rate_paise, r.single_rate_paise, r.inclusions) && (
                      <p className="quote-tariff">{tariffLine(r.nightly_rate_paise, r.single_rate_paise, r.inclusions)}</p>
                    )}
                    {r.bookable ? (
                      <>
                        <p className="quote-price">
                          <span className="quote-price__rate">{rupees(r.nightly_total_paise || r.nightly_rate_paise * r.room_count)}</span>
                          <span className="quote-price__unit">
                            {r.room_count > 1 ? `per night for ${plural(r.room_count, 'room')}`
                              : r.single_rate_paise != null ? `per night · ${r.single_rooms ? 'single' : 'double'} occupancy` : 'per night'}
                            {' · '}{rupees(r.total_paise)} for {plural(r.nights, 'night')}{r.tax_paise ? ' incl. taxes' : ''}
                          </span>
                        </p>
                        <button type="button" className="btn" onClick={() => setSelected(r)} style={{ alignSelf: 'flex-start' }}>
                          {selected?.slug === r.slug ? 'Selected' : 'Select'}
                        </button>
                      </>
                    ) : (
                      <p className="quote-unavailable">
                        {r.available_rooms > 0 && r.available_rooms < r.room_count
                          ? `Only ${plural(r.available_rooms, 'room')} left; your party needs ${r.room_count}`
                          : r.available_rooms > 0 ? 'This party is too large to book online. Please contact reservations.'
                          : 'Sold out for these dates'}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {selected && result.data && (
        <section className="section bg-alt" aria-labelledby="details-title" ref={detailsRef} id="details">
          <GuestDetails quote={selected} stay={result.data} onBooked={(ref, email) => {
            rememberBookingEmail(ref, email);
            navigate(`/booking/${ref}`, { state: { email, justPaid: true } });
          }} />
        </section>
      )}
    </>
  );
}

function GuestDetails({ quote, stay, onBooked }) {
  const { settings } = useSite();
  // "request": the hotel takes bookings as requests (emailed to reservations), no online payment
  const requestMode = stay.booking_mode === 'request';
  const idempotencyKey = useRef(uuid());
  const [pending, setPending] = useState(null); // {booking, checkout} after a dismissed checkout
  const navigate = useNavigate();
  const f = useForm(
    { guest_name: '', guest_email: '', guest_phone: '', special_requests: '', accept_terms: false },
    (v) => ({
      guest_name: rules.name(v.guest_name), guest_email: rules.email(v.guest_email), guest_phone: rules.phone(v.guest_phone),
      accept_terms: v.accept_terms ? null : 'Please accept the booking terms to continue',
    }),
    { resetOnSuccess: false },
  );

  // A new room or stay is a new checkout
  useEffect(() => { idempotencyKey.current = uuid(); setPending(null); }, [quote.slug, stay.check_in, stay.check_out]);

  const pay = async (created) => {
    const { booking, checkout } = created;
    const outcome = await openCheckout(checkout);
    if (outcome.status === 'success') {
      f.setStatus({ type: 'success', message: 'Payment received. Confirming your booking…' });
      try {
        await siteApi.verifyPayment(outcome.response);
      } catch (err) {
        // Verification problems are shown on the booking page, which re-checks with the server
        if (!(err instanceof ApiError)) throw err;
      }
      onBooked(booking.reference, booking.guest_email);
      return undefined;
    }
    siteApi.reportPayment({
      razorpay_order_id: checkout.order_id,
      outcome: outcome.failure ? 'failed' : 'dismissed',
      error_code: outcome.failure?.code?.slice(0, 64),
      error_description: outcome.failure?.description?.slice(0, 500),
      razorpay_payment_id: outcome.failure?.metadata?.payment_id,
    }).catch(() => {});
    setPending(created);
    throw new Error(outcome.failure
      ? `Payment was not completed: ${outcome.failure.description || 'the payment failed'}. You can try again.`
      : `Payment was not completed. Your room is held until ${timeOnly(booking.hold_expires_at)}.`);
  };

  const submit = f.submit(async (v) => {
    if (pending) return pay(pending);
    const body = {
      check_in: stay.check_in, check_out: stay.check_out, adults: stay.adults, children: stay.children,
      room_type_slug: quote.slug, room_count: quote.room_count, guest_name: v.guest_name.trim(), guest_email: v.guest_email.trim(),
      guest_phone: v.guest_phone.trim(), special_requests: v.special_requests.trim() || null, accept_terms: true,
    };
    let created;
    try {
      created = await siteApi.createBooking(body, idempotencyKey.current);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'sold_out') idempotencyKey.current = uuid();
      throw err;
    }
    if (!created.checkout) {                     // booking request recorded and emailed; nothing to pay
      onBooked(created.booking.reference, created.booking.guest_email);
      return undefined;
    }
    return pay(created);
  });

  return (
    <div className="wrap split split--top">
      <div className="stack">
        <p className="kicker">Your stay</p>
        <h2 id="details-title">{quote.room_count > 1 ? `${quote.room_count} × ${quote.name}` : quote.name}</h2>
        <dl className="contact-list">
          <div><dt>Check-in</dt><dd>{longDate(stay.check_in)}</dd></div>
          <div><dt>Check-out</dt><dd>{longDate(stay.check_out)}</dd></div>
          <div><dt>Guests</dt><dd>{guestsLabel(stay.adults, stay.children)}</dd></div>
          <div><dt>Rate</dt><dd>{rateBreakdown({ rate: quote.nightly_rate_paise, singleRate: quote.single_rate_paise, singles: quote.single_rooms, rooms: quote.room_count, nights: quote.nights })} = {rupees(quote.subtotal_paise)}</dd></div>
          {quote.inclusions && <div><dt>Includes</dt><dd>{quote.inclusions}</dd></div>}
          {quote.tax_paise > 0 && <div><dt>Taxes ({Number(quote.tax_percent)}%)</dt><dd>{rupees(quote.tax_paise)}</dd></div>}
          <div className="summary-total"><dt>Total</dt><dd>{rupees(quote.total_paise)}</dd></div>
        </dl>
        {settings.cancellation_policy && (
          <p className="hold-note"><strong>Cancellation policy.</strong> {settings.cancellation_policy}</p>
        )}
        {requestMode ? (
          <p className="hold-note">No payment is taken now. Send your request and our reservations team will contact you by phone or email to confirm your booking.</p>
        ) : (
          <p className="hold-note">Your room is held for 15 minutes once you continue to payment. Payments are processed securely by Razorpay; we never see or store your card details.</p>
        )}
      </div>

      <form className="form-panel" aria-labelledby="details-title" noValidate ref={f.formRef} onSubmit={submit}>
        <Field form={f} name="guest_name" label="Full name" type="text" autoComplete="name" />
        <Field form={f} name="guest_email" label="Email" type="email" autoComplete="email" />
        <Field form={f} name="guest_phone" label="Phone" type="tel" autoComplete="tel" />
        <Field form={f} name="special_requests" label="Special requests" as="textarea" className="field field--full"
          placeholder="Arrival time, accessibility needs…" maxLength={1000} />
        <Check form={f} name="accept_terms">I agree to the booking terms and the hotel’s cancellation policy.</Check>
        <FormStatus status={f.status} />
        <button className="btn" type="submit" disabled={f.submitting}>
          {requestMode
            ? (f.submitting ? 'Sending request…' : 'Send booking request')
            : (f.submitting ? 'Opening secure payment…' : pending ? 'Try payment again' : `Pay ${rupees(quote.total_paise)} securely`)}
        </button>
        {pending && (
          <button type="button" className="link" style={{ background: 'none', border: 0, gridColumn: '1 / -1', justifySelf: 'start' }}
            onClick={() => navigate(`/booking/${pending.booking.reference}`, { state: { email: pending.booking.guest_email } })}>
            View booking {pending.booking.reference}
          </button>
        )}
      </form>
    </div>
  );
}

/* /booking/:reference - the guest's view of one booking. Status always
   comes from the server; while a payment is being confirmed it re-checks
   every few seconds. Unpaid bookings can resume payment while held. */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Field, FormStatus, SubmitButton } from '../components/forms/Fields';
import { rules, useForm } from '../components/forms/useForm';
import { SplitText } from '../components/SplitText';
import { usePageMotion } from '../motion/usePageMotion';
import { ApiError, siteApi } from '../services/api';
import { openCheckout } from '../services/razorpay';
import { dateTime, guestsLabel, longDate, plural, rateBreakdown, rupees, timeOnly } from '../utils/format';
import { recallBookingEmail, rememberBookingEmail } from './bookingSession';

const COPY = {
  confirmed: { pill: 'confirmed', label: 'Confirmed', title: 'Your stay is confirmed', body: 'A confirmation has been sent to your email. We look forward to welcoming you.' },
  pending_payment: { pill: 'pending', label: 'Awaiting payment', title: 'Your room is on hold', body: '' },
  payment_review: { pill: 'pending', label: 'Payment received', title: 'Thank you, payment received', body: 'Our reservations team is finalising your room and will contact you shortly.' },
  expired: { pill: 'problem', label: 'Expired', title: 'This booking has expired', body: 'The room hold lapsed before payment was completed. No money was taken for this booking.' },
  cancelled: { pill: 'problem', label: 'Cancelled', title: 'This booking was cancelled', body: 'If you were charged, the refund is processed to your original payment method.' },
};

export default function BookingStatus() {
  const { reference } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState(() => location.state?.email || recallBookingEmail(reference));
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(!!email);
  const [paying, setPaying] = useState(false);
  const [payMsg, setPayMsg] = useState(null);
  const polls = useRef(0);
  usePageMotion(!loading);

  const load = useCallback(async (silent = false) => {
    if (!email) return null;
    if (!silent) setLoading(true);
    try {
      const b = await siteApi.lookupBooking(reference, email);
      setBooking(b);
      setError(null);
      return b;
    } catch (err) {
      setError(err);
      return null;
    } finally {
      if (!silent) setLoading(false);
    }
  }, [reference, email]);

  useEffect(() => { load(); }, [load]);

  // Right after checkout the capture can take a few seconds (or arrive by webhook)
  const awaiting = booking && booking.status === 'pending_payment'
    && ['authorized', 'captured'].includes(booking.payment_status);
  useEffect(() => {
    if (!awaiting || polls.current > 20) return undefined;
    const t = setTimeout(() => { polls.current += 1; load(true); }, 3000);
    return () => clearTimeout(t);
  }, [awaiting, booking, load]);

  const resumePayment = async () => {
    setPaying(true);
    setPayMsg(null);
    try {
      const { checkout } = await siteApi.retryPayment(reference, email);
      const outcome = await openCheckout(checkout);
      if (outcome.status === 'success') {
        await siteApi.verifyPayment(outcome.response).catch((err) => { if (!(err instanceof ApiError)) throw err; });
        polls.current = 0;
        await load(true);
      } else {
        siteApi.reportPayment({ razorpay_order_id: checkout.order_id, outcome: outcome.failure ? 'failed' : 'dismissed',
          error_description: outcome.failure?.description?.slice(0, 500) }).catch(() => {});
        setPayMsg({ type: 'error', message: 'Payment was not completed. You can try again while your room is held.' });
      }
    } catch (err) {
      setPayMsg({ type: 'error', message: err.message });
      if (err instanceof ApiError && err.code === 'booking_expired') load(true);
    } finally {
      setPaying(false);
    }
  };

  if (!email) {
    return <AskEmail reference={reference} onEmail={(e) => { rememberBookingEmail(reference, e); setEmail(e); }} />;
  }

  const copy = booking ? COPY[booking.status] || COPY.pending_payment : null;
  const held = booking?.status === 'pending_payment' && booking.hold_expires_at;

  return (
    <>
      <section className="page-head" aria-labelledby="page-title">
        <div className="wrap">
          <p className="kicker" data-hero-fade="">Booking {reference}</p>
          {booking
            ? <SplitText key={copy.title} as="h1" id="page-title" mode="lines" text={awaiting ? 'Confirming your payment' : copy.title} />
            : <h1 id="page-title">{loading ? 'Finding your booking…' : 'Booking not found'}</h1>}
        </div>
      </section>

      <section className="section book-flow" style={{ paddingTop: 0 }}>
        <div className="wrap split split--top">
          {error && !booking && (
            <div className="stack">
              <p className="state-msg state-msg--error" role="alert">{error.message}</p>
              <div className="actions">
                <button type="button" className="btn" onClick={() => { setEmail(''); setError(null); }}>Try another email</button>
                <Link className="btn btn--ghost" style={{ '--btn-fg': 'var(--c-heading)' }} to="/contact">Contact us</Link>
              </div>
            </div>
          )}
          {booking && (
            <>
              <div className="stack">
                <span className={`status-pill status-pill--${awaiting ? 'pending' : copy.pill}`} role="status">
                  {awaiting && <span className="spinner" aria-hidden="true" />}
                  {awaiting ? 'Confirming payment' : copy.label}
                </span>
                <p className="intro__body">
                  {awaiting ? 'Your payment has been received and is being confirmed. This page updates automatically.'
                    : held ? `Complete payment by ${timeOnly(booking.hold_expires_at)} to confirm your room. After that the hold is released.`
                      : copy.body}
                </p>
                {held && !awaiting && (
                  <div className="actions">
                    <button type="button" className="btn" onClick={resumePayment} disabled={paying}>
                      {paying ? 'Opening secure payment…' : `Pay ${rupees(booking.total_paise)} securely`}
                    </button>
                  </div>
                )}
                {payMsg && <FormStatus status={payMsg} />}
                {booking.status === 'expired' && (
                  <div className="actions">
                    <button type="button" className="btn" onClick={() => navigate(`/book?check_in=${booking.check_in}&check_out=${booking.check_out}&adults=${booking.adults}&children=${booking.children}&room=${booking.room_type_slug}`)}>
                      Search again
                    </button>
                  </div>
                )}
              </div>
              <dl className="contact-list">
                <div><dt>Reference</dt><dd>{booking.reference}</dd></div>
                <div><dt>Room</dt><dd>{booking.room_count > 1 ? `${booking.room_count} × ${booking.room_type_name}` : booking.room_type_name}</dd></div>
                <div><dt>Check-in</dt><dd>{longDate(booking.check_in)}</dd></div>
                <div><dt>Check-out</dt><dd>{longDate(booking.check_out)} · {plural(booking.nights, 'night')}</dd></div>
                <div><dt>Guests</dt><dd>{guestsLabel(booking.adults, booking.children)}</dd></div>
                {booking.single_room_count > 0 && (
                  <div><dt>Rate</dt><dd>{rateBreakdown({ rate: booking.nightly_rate_paise, singleRate: booking.single_rate_paise, singles: booking.single_room_count, rooms: booking.room_count, nights: booking.nights })}</dd></div>
                )}
                {booking.inclusions && <div><dt>Includes</dt><dd>{booking.inclusions}</dd></div>}
                <div><dt>Guest</dt><dd>{booking.guest_name}<br />{booking.guest_email} · {booking.guest_phone}</dd></div>
                {booking.special_requests && <div><dt>Requests</dt><dd>{booking.special_requests}</dd></div>}
                {booking.tax_paise > 0 && <div><dt>Taxes</dt><dd>{rupees(booking.tax_paise)}</dd></div>}
                <div className="summary-total"><dt>{booking.status === 'confirmed' ? 'Paid' : 'Total'}</dt><dd>{rupees(booking.total_paise)}</dd></div>
                {booking.confirmed_at && <div><dt>Confirmed</dt><dd>{dateTime(booking.confirmed_at)}</dd></div>}
                {booking.cancellation_policy && <div><dt>Cancellation policy</dt><dd>{booking.cancellation_policy}</dd></div>}
              </dl>
            </>
          )}
        </div>
      </section>
    </>
  );
}

function AskEmail({ reference, onEmail }) {
  usePageMotion(true);
  const f = useForm({ email: '' }, (v) => ({ email: rules.email(v.email) }), { resetOnSuccess: false });
  return (
    <>
      <section className="page-head" aria-labelledby="page-title">
        <div className="wrap">
          <p className="kicker" data-hero-fade="">Booking {reference}</p>
          <SplitText as="h1" id="page-title" mode="lines" text="Confirm your email" />
        </div>
      </section>
      <section className="section book-flow" style={{ paddingTop: 0 }}>
        <div className="wrap split split--top">
          <p className="intro__body">For your privacy, enter the email address used to make this booking.</p>
          <form className="form-panel" noValidate ref={f.formRef} onSubmit={f.submit(async (v) => { onEmail(v.email.trim()); })}>
            <Field form={f} name="email" label="Email" type="email" autoComplete="email" className="field field--full" />
            <FormStatus status={f.status} />
            <SubmitButton form={f} busyLabel="Checking…">View booking</SubmitButton>
          </form>
        </div>
      </section>
    </>
  );
}

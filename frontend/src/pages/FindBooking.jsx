import { useNavigate } from 'react-router-dom';
import { Field, FormStatus, SubmitButton } from '../components/forms/Fields';
import { rules, useForm } from '../components/forms/useForm';
import { SplitText } from '../components/SplitText';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';
import { rememberBookingEmail } from './bookingSession';

export default function FindBooking() {
  usePageMotion(true);
  const navigate = useNavigate();
  const f = useForm({ reference: '', email: '' }, (v) => ({
    reference: /^TYC[A-Z0-9]{8}$/i.test(v.reference.trim()) ? null : 'Enter the reference from your confirmation, e.g. TYCAB12CD34',
    email: rules.email(v.email),
  }), { resetOnSuccess: false });

  return (
    <>
      <section className="page-head" aria-labelledby="page-title">
        <div className="wrap">
          <p className="kicker" data-hero-fade="">Reservations</p>
          <SplitText as="h1" id="page-title" mode="lines" text="Find your booking" />
        </div>
      </section>
      <section className="section book-flow" style={{ paddingTop: 0 }}>
        <div className="wrap split split--top">
          <div className="stack">
            <p className="intro__body">Enter your booking reference and the email address you booked with to see your booking, or to complete a payment that was interrupted.</p>
          </div>
          <form className="form-panel" noValidate ref={f.formRef} onSubmit={f.submit(async (v) => {
            const ref = v.reference.trim().toUpperCase();
            const b = await siteApi.lookupBooking(ref, v.email.trim());
            rememberBookingEmail(b.reference, v.email.trim());
            navigate(`/booking/${b.reference}`, { state: { email: v.email.trim() } });
            return undefined;
          })}>
            <Field form={f} name="reference" label="Booking reference" type="text" autoComplete="off"
              autoCapitalize="characters" spellCheck={false} maxLength={16} />
            <Field form={f} name="email" label="Email" type="email" autoComplete="email" />
            <FormStatus status={f.status} />
            <SubmitButton form={f} busyLabel="Searching…">Find Booking</SubmitButton>
          </form>
        </div>
      </section>
    </>
  );
}

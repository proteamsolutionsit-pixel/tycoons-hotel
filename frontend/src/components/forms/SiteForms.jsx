/* The request forms from the original design, now wired to the API.
   Fields, labels and option lists are exactly the original's. */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { siteApi } from '../../services/api';
import { hotelToday } from '../../utils/format';
import { Check, Field, FieldError, FormStatus, SubmitButton } from './Fields';
import { rules, useForm } from './useForm';

const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== '' && v !== null && v !== undefined));

/* Fishy Tales: Reserve a table ------------------------------------------- */
export function ReserveTableForm() {
  const today = hotelToday();
  const f = useForm(
    { name: '', phone: '', date: '', time: '', guests: '2', occasion: 'None', requests: '' },
    (v) => ({ name: rules.name(v.name), phone: rules.phone(v.phone), date: rules.futureDate(v.date, today), time: rules.time(v.time) }),
  );
  return (
    <form className="form-panel" aria-labelledby="reserve-title" data-reveal="" noValidate ref={f.formRef}
      onSubmit={f.submit(async (v) => (await siteApi.tableReservation(clean(v))).message)}>
      <Field form={f} name="name" label="Full name" type="text" autoComplete="name" />
      <Field form={f} name="phone" label="Phone" type="tel" autoComplete="tel" />
      <Field form={f} name="date" label="Date" type="date" min={today} />
      <Field form={f} name="time" label="Time" type="time" />
      <Field form={f} name="guests" label="Guests" as="select">
        <option value="2">2 guests</option><option value="3">3 guests</option><option value="4">4 guests</option>
        <option value="5-8">5–8 guests</option><option value="9+">9+ guests</option>
      </Field>
      <Field form={f} name="occasion" label="Occasion" as="select">
        {['None', 'Birthday', 'Anniversary', 'Business dinner', 'Other'].map((o) => <option key={o}>{o}</option>)}
      </Field>
      <Field form={f} name="requests" label="Special requests" as="textarea" className="field field--full"
        placeholder="Dietary needs, seating preference…" maxLength={1000} />
      <FormStatus status={f.status} />
      <SubmitButton form={f}>Request Reservation</SubmitButton>
    </form>
  );
}

/* Kai Wellness Spa: Book a treatment -------------------------------------- */
// Mount with key={...} once treatments load, so the default is the first
// treatment (as in the original <select>) and a reset returns to it.
export function SpaAppointmentForm({ treatments }) {
  const today = hotelToday();
  const first = treatments?.[0]?.id;
  const f = useForm(
    { name: '', phone: '', treatment_id: first ? String(first) : 'advise', guest_type: 'hotel_guest', date: '', time: '' },
    (v) => ({ name: rules.name(v.name), phone: rules.phone(v.phone), date: rules.futureDate(v.date, today), time: rules.time(v.time) }),
  );

  return (
    <form className="form-panel" aria-labelledby="book-spa-title" data-reveal="" noValidate ref={f.formRef}
      onSubmit={f.submit(async (v) => {
        const body = { ...clean(v), treatment_id: v.treatment_id === 'advise' || !v.treatment_id ? null : Number(v.treatment_id) };
        const res = await siteApi.spaAppointment(body);
        return res.message;
      })}>
      <Field form={f} name="name" label="Full name" type="text" autoComplete="name" />
      <Field form={f} name="phone" label="Phone" type="tel" autoComplete="tel" />
      <Field form={f} name="treatment_id" label="Treatment" as="select">
        {(treatments || []).map((t) => <option key={t.id} value={t.id}>{t.form_label}</option>)}
        <option value="advise">Not sure — advise me</option>
      </Field>
      <Field form={f} name="guest_type" label="Guest type" as="select">
        <option value="hotel_guest">Hotel guest</option><option value="visitor">Visitor</option>
      </Field>
      <Field form={f} name="date" label="Date" type="date" min={today} />
      <Field form={f} name="time" label="Preferred time" type="time" />
      <FormStatus status={f.status} />
      <SubmitButton form={f}>Request Appointment</SubmitButton>
    </form>
  );
}

/* Business Lounge: Plan your business stay -------------------------------- */
export function BusinessEnquiryForm() {
  const today = hotelToday();
  const f = useForm(
    { company: '', name: '', email: '', phone: '', date: '', attendees: '', requirements: '' },
    (v) => ({
      company: rules.required(v.company, 'Please enter your company name'),
      name: rules.name(v.name), email: rules.email(v.email), phone: rules.phone(v.phone),
      date: v.date && v.date < today ? 'Choose today or a later date' : null,
      attendees: v.attendees && (Number(v.attendees) < 1 || !Number.isInteger(Number(v.attendees))) ? 'Enter a number of guests' : null,
    }),
  );
  return (
    <form className="form-panel" aria-labelledby="proposal-title" data-reveal="" noValidate ref={f.formRef}
      onSubmit={f.submit(async (v) => {
        const body = clean({ ...v, attendees: v.attendees ? Number(v.attendees) : '' });
        return (await siteApi.businessEnquiry(body)).message;
      })}>
      <Field form={f} name="company" label="Company" type="text" autoComplete="organization" />
      <Field form={f} name="name" label="Contact name" type="text" autoComplete="name" />
      <Field form={f} name="email" label="Email" type="email" autoComplete="email" />
      <Field form={f} name="phone" label="Phone" type="tel" autoComplete="tel" />
      <Field form={f} name="date" label="Arrival date" type="date" min={today} />
      <Field form={f} name="attendees" label="Guests" type="number" min="1" inputMode="numeric" />
      <Field form={f} name="requirements" label="Requirements" as="textarea" className="field field--full"
        placeholder="Accommodation, lounge access, client dinners…" maxLength={2000} />
      <FormStatus status={f.status} />
      <SubmitButton form={f}>Send Request</SubmitButton>
    </form>
  );
}

/* Careers: Send your application ----------------------------------------- */
export function ApplicationForm() {
  const location = useLocation();
  const f = useForm(
    { name: '', email: '', phone: '', position: '', opening_id: '', cv: null, message: '', consent: false },
    (v) => ({
      name: rules.name(v.name), email: rules.email(v.email), phone: rules.phone(v.phone),
      position: rules.required(v.position, 'Please tell us which position you are applying for'),
      cv: v.cv && !/\.(pdf|docx?)$/i.test(v.cv.name) ? 'Please upload a PDF or Word file'
        : v.cv && v.cv.size > 5 * 1024 * 1024 ? 'The file is too large (max 5 MB)' : null,
      consent: v.consent ? null : 'Please agree to your details being used for this application',
    }),
    { fieldMap: { file: 'cv' } },
  );

  // "Apply" on an opening prefills the position
  useEffect(() => {
    const s = location.state;
    if (s && s.position) {
      f.set('position', s.position);
      f.set('opening_id', s.openingId ? String(s.openingId) : '');
    }
  }, [location.key]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <form className="form-panel" aria-labelledby="apply-title" data-reveal="" noValidate ref={f.formRef}
      onSubmit={f.submit(async (v) => {
        const fd = new FormData();
        ['name', 'email', 'phone', 'position', 'message'].forEach((k) => v[k] && fd.append(k, v[k]));
        if (v.opening_id) fd.append('opening_id', v.opening_id);
        fd.append('consent', v.consent ? 'true' : 'false');
        if (v.cv) fd.append('cv', v.cv);
        return (await siteApi.jobApplication(fd)).message;
      })}>
      <Field form={f} name="name" label="Full name" type="text" autoComplete="name" />
      <Field form={f} name="email" label="Email" type="email" autoComplete="email" />
      <Field form={f} name="phone" label="Phone" type="tel" autoComplete="tel" />
      <Field form={f} name="position" label="Position" type="text" maxLength={120} />
      <label className="field field--full">CV (PDF or Word)
        <input {...f.bind('cv', { type: 'file' })} accept=".pdf,.doc,.docx" />
        <FieldError form={f} name="cv" />
      </label>
      <Field form={f} name="message" label="Message" as="textarea" className="field field--full"
        placeholder="Tell us a little about yourself" maxLength={4000} />
      <Check form={f} name="consent">I agree to my details being used for this application.</Check>
      <FormStatus status={f.status} />
      <SubmitButton form={f}>Send Application</SubmitButton>
    </form>
  );
}

/* Contact: Enquiry -------------------------------------------------------- */
export function ContactForm() {
  const f = useForm(
    { name: '', email: '', phone: '', topic: 'Room reservation', message: '', consent: false },
    (v) => ({
      name: rules.name(v.name), email: rules.email(v.email), phone: rules.optionalPhone(v.phone),
      message: !v.message.trim() ? 'Please tell us how we can help' : v.message.trim().length < 5 ? 'Please tell us a little more' : null,
      consent: v.consent ? null : 'Please agree to be contacted about your enquiry',
    }),
  );
  return (
    <form className="form-panel" aria-label="Enquiry" data-reveal="" noValidate ref={f.formRef}
      onSubmit={f.submit(async (v) => (await siteApi.contactEnquiry(clean(v))).message)}>
      <Field form={f} name="name" label="Full name" type="text" autoComplete="name" />
      <Field form={f} name="email" label="Email" type="email" autoComplete="email" />
      <Field form={f} name="phone" label="Phone" type="tel" autoComplete="tel" />
      <Field form={f} name="topic" label="Enquiry about" as="select">
        {['Room reservation', 'Business lounge', 'Fishy Tales', 'Kai Wellness Spa', 'Other'].map((o) => <option key={o}>{o}</option>)}
      </Field>
      <Field form={f} name="message" label="Message" as="textarea" className="field field--full" placeholder="How can we help?" maxLength={2000} />
      <Check form={f} name="consent">I agree to be contacted about my enquiry.</Check>
      <FormStatus status={f.status} />
      <SubmitButton form={f}>Send Enquiry</SubmitButton>
    </form>
  );
}

/* Homepage newsletter ------------------------------------------------------ */
export function NewsletterForm() {
  const f = useForm({ email: '', consent: false }, (v) => ({
    email: rules.email(v.email),
    consent: v.consent ? null : 'Please tick the box to confirm your subscription',
  }));
  return (
    <form className="newsletter__form" data-reveal="" noValidate ref={f.formRef}
      onSubmit={f.submit(async (v) => (await siteApi.newsletter(v)).message)}>
      <label className="newsletter__label" htmlFor="nl-email">Email address</label>
      <div className="newsletter__row">
        <input className="input" id="nl-email" type="email" placeholder="you@company.com" autoComplete="email" {...f.bind('email')} />
        <SubmitButton form={f} busyLabel="Subscribing…">Subscribe</SubmitButton>
      </div>
      <FieldError form={f} name="email" />
      <label className="check"><input {...f.bind('consent', { type: 'checkbox' })} />Yes, subscribe me to the newsletter.</label>
      <FieldError form={f} name="consent" />
      <FormStatus status={f.status} />
    </form>
  );
}

import { useCallback, useId, useRef, useState } from 'react';
import { ApiError } from '../../services/api';

/**
 * Small form state helper.
 *   const f = useForm(initial, validate)
 *   <input {...f.bind('email')} />
 *   <form onSubmit={f.submit(async (values) => api(...))}>
 * Server 422 details ({field, message}) are mapped back onto the fields;
 * `fieldMap` renames API field names to form field names where they differ.
 */
export function useForm(initial, validate, { fieldMap = {}, resetOnSuccess = true } = {}) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef(null);
  const uid = useId();

  const set = useCallback((name, value) => {
    setValues((v) => ({ ...v, [name]: value }));
    setErrors((e) => (e[name] ? { ...e, [name]: undefined } : e));
  }, []);

  const errId = (name) => `${uid}-${name}-err`;

  const bind = (name, { type } = {}) => {
    const common = {
      name,
      'aria-invalid': errors[name] ? true : undefined,
      'aria-describedby': errors[name] ? errId(name) : undefined,
    };
    if (type === 'checkbox') {
      return { ...common, type: 'checkbox', checked: !!values[name], onChange: (e) => set(name, e.target.checked) };
    }
    if (type === 'file') {
      return { ...common, type: 'file', onChange: (e) => set(name, e.target.files?.[0] || null) };
    }
    return { ...common, value: values[name] ?? '', onChange: (e) => set(name, e.target.value) };
  };

  const focusFirstError = (errs) => {
    requestAnimationFrame(() => {
      const first = Object.keys(errs).find((k) => errs[k]);
      const el = first && formRef.current?.querySelector(`[name="${first}"]`);
      el?.focus();
    });
  };

  const submit = (handler) => async (e) => {
    e.preventDefault();
    if (submitting) return;
    setStatus(null);
    const clientErrors = validate ? validate(values) : {};
    const has = Object.values(clientErrors).some(Boolean);
    setErrors(clientErrors);
    if (has) {
      setStatus({ type: 'error', message: 'Please check the highlighted fields.' });
      focusFirstError(clientErrors);
      return;
    }
    setSubmitting(true);
    try {
      const result = await handler(values);
      const message = typeof result === 'string' ? result : result?.message;
      if (message !== undefined) setStatus({ type: 'success', message });
      if (resetOnSuccess) {
        setValues(initial);
        formRef.current?.reset();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        const fe = {};
        Object.entries(err.fieldErrors).forEach(([k, msg]) => { fe[fieldMap[k] || k] = msg; });
        setErrors(fe);
        setStatus({ type: 'error', message: err.message });
        focusFirstError(fe);
      } else if (err?.name !== 'AbortError') {
        setStatus({ type: 'error', message: err?.message || 'Something went wrong. Please try again.' });
      }
    } finally {
      setSubmitting(false);
    }
  };

  return { values, set, setValues, errors, setErrors, status, setStatus, submitting, bind, submit, formRef, errId };
}

/* Client-side checks that mirror the API's rules */
export const rules = {
  required: (v, msg = 'This field is required') => (v === undefined || v === null || String(v).trim() === '' ? msg : null),
  name: (v) => (!v || v.trim().length < 2 ? 'Please enter your full name' : /[<>{}[\]\\=;]/.test(v) ? 'Please use letters, spaces and basic punctuation only' : null),
  email: (v) => (!v ? 'Please enter your email' : /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()) ? null : 'Please enter a valid email address'),
  phone: (v) => (!v ? 'Please enter your phone number'
    : /^\+?[0-9 ()-]{7,20}$/.test(v.trim()) && (v.match(/\d/g) || []).length >= 7 ? null : 'Please enter a valid phone number'),
  optionalPhone: (v) => (v ? rules.phone(v) : null),
  futureDate: (v, today) => (!v ? 'Please choose a date' : v < today ? 'Choose today or a later date' : null),
  time: (v) => (!v ? 'Please choose a time' : null),
};

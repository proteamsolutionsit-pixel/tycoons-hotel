/* Field wrappers matching the original markup: <label class="field">Label <input></label> */

export function FieldError({ form, name, className = 'field-error' }) {
  const msg = form.errors[name];
  if (!msg) return null;
  return <span className={className} id={form.errId(name)} role="alert">{msg}</span>;
}

export function Field({ form, name, label, className = 'field', as = 'input', children, ...props }) {
  const bound = form.bind(name, { type: props.type });
  let control;
  if (as === 'select') control = <select {...bound} {...props}>{children}</select>;
  else if (as === 'textarea') control = <textarea {...bound} {...props} />;
  else control = <input {...bound} {...props} />;
  return (
    <label className={className}>{label}
      {control}
      <FieldError form={form} name={name} />
    </label>
  );
}

export function Check({ form, name, children }) {
  return (
    <>
      <label className="check"><input {...form.bind(name, { type: 'checkbox' })} />{children}</label>
      <FieldError form={form} name={name} className="field-error field-error--check" />
    </>
  );
}

export function FormStatus({ status }) {
  if (!status) return null;
  return (
    <p className={`form-status form-status--${status.type}`} role={status.type === 'error' ? 'alert' : 'status'}>
      {status.message}
    </p>
  );
}

export function SubmitButton({ form, children, className = 'btn', busyLabel = 'Sending…' }) {
  return (
    <button className={className} type="submit" disabled={form.submitting} aria-busy={form.submitting || undefined}>
      {form.submitting ? busyLabel : children}
    </button>
  );
}

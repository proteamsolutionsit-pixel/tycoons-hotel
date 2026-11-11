/* Payment gateway: test payments or Razorpay, and the Razorpay keys.
   Secrets are write-only: the API says whether one is saved, never what it is. */
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../services/api';
import { useAuth } from '../auth';
import { ConfirmDialog, Notice, PageTitle, useToast } from '../ui';

const URL = '/api/v1/admin/payment-settings';
const EVENTS = ['payment.authorized', 'payment.captured', 'payment.failed', 'order.paid', 'refund.processed', 'refund.failed'];

const STATUS = {
  mock: ['info', 'Test payments', 'No real money moves. Guests see a test payment window where they choose “success” or “failure”.'],
  test: ['good', 'Razorpay test mode', 'Payments go through Razorpay’s test environment. Use Razorpay’s test cards or UPI IDs; nobody is charged.'],
  live: ['warn', 'Razorpay LIVE', 'Guests are charged real money.'],
  request: ['info', 'Booking requests by email', 'Guests send a booking request instead of paying online. Each request is emailed to the addresses in Site settings → Booking request emails, and staff confirm it under Bookings.'],
  disabled: ['error', 'Online payments are off', 'Guests can’t pay for bookings until a payment mode is set up below.'],
};

function randomSecret() {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

export default function PaymentSettings() {
  const { handleError } = useAuth();
  const toast = useToast();
  const [cfg, setCfg] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [form, setForm] = useState({ mode: 'razorpay', key_id: '', key_secret: '', webhook_secret: '' });
  const [errors, setErrors] = useState({});
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState('');
  const [confirm, setConfirm] = useState(null);   // 'live' | 'reset'

  const apply = useCallback((data) => {
    setCfg(data);
    setForm({ mode: data.mode, key_id: data.key_id, key_secret: '', webhook_secret: '' });
    setErrors({});
  }, []);

  useEffect(() => {
    api.get(URL).then(apply).catch((err) => { handleError(err); setLoadError(err.message); });
  }, [apply, handleError]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const fail = (err) => { handleError(err); setErrors(err.fieldErrors || {}); setNotice({ type: 'error', message: err.message }); };

  const save = async (confirmLive = false) => {
    setBusy('save'); setNotice(null); setErrors({});
    try {
      const body = form.mode !== 'razorpay' ? { mode: form.mode } : {
        mode: 'razorpay', key_id: form.key_id.trim(), key_secret: form.key_secret || null,
        webhook_secret: form.webhook_secret || null, confirm_live: confirmLive,
      };
      apply(await api.put(URL, body));
      setConfirm(null);
      toast('Payment settings saved');
    } catch (err) { setConfirm(null); fail(err); } finally { setBusy(''); }
  };

  const submit = (e) => {
    e.preventDefault();
    const goingLive = form.mode === 'razorpay' && form.key_id.trim().startsWith('rzp_live_') && cfg.key_kind !== 'live';
    if (goingLive) setConfirm('live'); else save();
  };

  const test = async () => {
    setBusy('test'); setNotice(null);
    try {
      const r = await api.post(`${URL}/test`, { key_id: form.key_id.trim(), key_secret: form.key_secret || null });
      setNotice({ type: r.ok ? 'success' : 'error', message: r.message });
    } catch (err) { fail(err); } finally { setBusy(''); }
  };

  const reset = async () => {
    setBusy('reset'); setNotice(null);
    try { apply(await api.del(URL)); setConfirm(null); toast('Using the server configuration again'); } catch (err) { setConfirm(null); fail(err); } finally { setBusy(''); }
  };

  if (loadError) return <><PageTitle title="Payment gateway" /><p className="adm-error">{loadError}</p></>;
  if (!cfg) return <><PageTitle title="Payment gateway" /><p className="adm-muted">Loading…</p></>;

  const [tone, heading, text] = STATUS[cfg.active] || STATUS.disabled;
  const sameKey = form.key_id.trim() === cfg.key_id;
  const secretSaved = cfg.has_key_secret && sameKey;
  const field = (name, label, input, hint) => (
    <div className="adm-field adm-field--wide">
      <label htmlFor={`pg-${name}`}>{label}</label>
      {input}
      {hint && <small className="adm-muted">{hint}</small>}
      {errors[name] && <small className="adm-error" role="alert">{errors[name]}</small>}
    </div>
  );

  return (
    <>
      <PageTitle title="Payment gateway" subtitle="How guests pay for room bookings" />

      <div className={`adm-notice adm-notice--${tone === 'warn' ? 'error' : tone === 'good' ? 'success' : tone}`} role="status">
        <span>
          <strong>Now active: {heading}.</strong> {text}
          {cfg.active === 'disabled' && !cfg.secrets_readable && ' The saved keys can’t be read on this server any more (the encryption key changed). Enter them again.'}
          <br />
          <small>
            {cfg.source === 'admin'
              ? `Set on this page${cfg.updated_by ? ` by ${cfg.updated_by}` : ''}${cfg.updated_at ? `, ${new Date(cfg.updated_at + 'Z').toLocaleString('en-IN')}` : ''}.`
              : 'Set in the server’s configuration file. Saving here takes over from it.'}
          </small>
        </span>
      </div>

      <form className="adm-form" style={{ maxWidth: 720, marginTop: 20 }} onSubmit={submit} noValidate>
        <Notice notice={notice} onClose={() => setNotice(null)} />
        <fieldset className="adm-field adm-field--wide" style={{ border: 0, padding: 0, margin: 0 }}>
          <legend className="adm-muted" style={{ fontSize: '0.8125rem', fontWeight: 500, marginBottom: 6 }}>Payment mode</legend>
          <div className="adm-field adm-field--check">
            <input id="pg-mode-razorpay" type="radio" name="mode" value="razorpay" checked={form.mode === 'razorpay'} onChange={set('mode')} />
            <label htmlFor="pg-mode-razorpay">Razorpay (test or live keys)</label>
          </div>
          <div className="adm-field adm-field--check">
            <input id="pg-mode-request" type="radio" name="mode" value="request" checked={form.mode === 'request'} onChange={set('mode')} />
            <label htmlFor="pg-mode-request">Booking requests by email (no online payment)</label>
          </div>
          <div className="adm-field adm-field--check">
            <input id="pg-mode-mock" type="radio" name="mode" value="mock" checked={form.mode === 'mock'} onChange={set('mode')} disabled={!cfg.mock_allowed} />
            <label htmlFor="pg-mode-mock">Test payments without Razorpay{!cfg.mock_allowed && ' (not available on the production site)'}</label>
          </div>
          {errors.mode && <small className="adm-error" role="alert">{errors.mode}</small>}
        </fieldset>

        {form.mode === 'razorpay' && (
          <>
            {field('key_id', 'Key Id',
              <input id="pg-key_id" className="adm-input adm-mono" autoComplete="off" spellCheck={false} placeholder="rzp_test_…"
                value={form.key_id} onChange={set('key_id')} />,
              'Starts with rzp_test_ (test mode) or rzp_live_ (real payments).')}
            {field('key_secret', 'Key Secret',
              <input id="pg-key_secret" className="adm-input adm-mono" type="password" autoComplete="new-password" spellCheck={false}
                placeholder={secretSaved ? 'Saved. Leave blank to keep it' : 'Paste the Key Secret'} value={form.key_secret} onChange={set('key_secret')} />,
              'Stored encrypted. It is never shown again, here or anywhere else.')}
            {field('webhook_secret', 'Webhook secret',
              <div style={{ display: 'flex', gap: 8 }}>
                <input id="pg-webhook_secret" className="adm-input adm-mono" type="text" autoComplete="off" spellCheck={false} style={{ flex: 1 }}
                  placeholder={cfg.has_webhook_secret ? 'Saved. Leave blank to keep it' : 'Choose one, or press Generate'}
                  value={form.webhook_secret} onChange={set('webhook_secret')} />
                <button type="button" className="adm-btn adm-btn--ghost" onClick={() => setForm((f) => ({ ...f, webhook_secret: randomSecret() }))}>Generate</button>
              </div>,
              'Enter exactly the same value in Razorpay when you add the webhook (see the steps below). Copy it before saving: it is hidden afterwards.')}
            <div className="adm-field adm-field--wide">
              <label htmlFor="pg-webhook-url">Webhook URL (for Razorpay)</label>
              <input id="pg-webhook-url" className="adm-input adm-mono" readOnly value={cfg.webhook_url} onFocus={(e) => e.target.select()} />
            </div>
          </>
        )}

        <div className="adm-form__actions" style={{ justifyContent: 'flex-start', flexWrap: 'wrap' }}>
          <button className="adm-btn" type="submit" disabled={!!busy}>{busy === 'save' ? 'Saving…' : 'Save'}</button>
          {form.mode === 'razorpay' && (
            <button type="button" className="adm-btn adm-btn--ghost" onClick={test} disabled={!!busy}>{busy === 'test' ? 'Checking…' : 'Test connection'}</button>
          )}
          {cfg.source === 'admin' && (
            <button type="button" className="adm-btn adm-btn--ghost" onClick={() => setConfirm('reset')} disabled={!!busy}>Use server configuration</button>
          )}
        </div>
      </form>

      <section className="adm-section" style={{ maxWidth: 720 }}>
        <h2 style={{ fontSize: '1.45rem', marginBottom: 12 }}>Getting your Razorpay keys</h2>
        <ol>
          <li>Sign in at <strong>dashboard.razorpay.com</strong>. Use the <strong>Test mode</strong> switch at the top for test keys; live keys are available once Razorpay has activated your account.</li>
          <li>Go to <strong>Account &amp; Settings → API Keys → Generate Key</strong>. Copy the <strong>Key Id</strong> and <strong>Key Secret</strong> into the fields above.</li>
          <li>Press <strong>Generate</strong> next to Webhook secret and copy the value.</li>
          <li>In Razorpay, open <strong>Account &amp; Settings → Webhooks → Add New Webhook</strong>. Paste the Webhook URL above, paste the same webhook secret, and tick these events: {EVENTS.map((e, i) => <span key={e}><code className="adm-mono">{e}</code>{i < EVENTS.length - 1 ? ', ' : ''}</span>)}.</li>
          <li>Back here, press <strong>Test connection</strong>, then <strong>Save</strong>.</li>
        </ol>
        <p className="adm-muted">Test keys and live keys are separate pairs, and each mode has its own webhook in Razorpay. When you move to live keys, set up the webhook again in live mode.
          Bookings already waiting for payment when you switch modes can’t be paid; their room holds lapse within 15 minutes and the guest can book again.</p>
      </section>

      {confirm === 'live' && (
        <ConfirmDialog title="Switch to live payments?" confirmLabel="Use live keys" danger confirmText="LIVE" busy={busy === 'save'}
          onConfirm={() => save(true)} onCancel={() => setConfirm(null)}>
          <p>From now on guests are charged <strong>real money</strong> for bookings on {cfg.webhook_url.replace(/^https?:\/\/([^/]+).*$/, '$1')}.</p>
          {cfg.environment !== 'production' && <p>This is the <strong>{cfg.environment}</strong> site. Live keys are normally used only on the production site.</p>}
        </ConfirmDialog>
      )}
      {confirm === 'reset' && (
        <ConfirmDialog title="Use the server configuration?" confirmLabel="Remove settings" busy={busy === 'reset'}
          onConfirm={reset} onCancel={() => setConfirm(null)}>
          <p>The mode and keys saved on this page are deleted, and the values in the server’s configuration file apply again.</p>
        </ConfirmDialog>
      )}
    </>
  );
}

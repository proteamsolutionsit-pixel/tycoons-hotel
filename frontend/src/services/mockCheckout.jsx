/* Test payment window (server in PAYMENT_MODE=mock). Plays the part of
   Razorpay Checkout: the customer chooses success or failure, the server
   records it and returns a signed response, and the booking page then
   verifies it through the normal /payments/verify call. No money moves. */
import { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { rupees } from '../utils/format';

function MockCheckout({ config, onDone }) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState(null);
  const [error, setError] = useState(null);
  const panel = useRef(null);

  useEffect(() => {
    panel.current?.querySelector('[data-autofocus]')?.focus();
    const onKey = (e) => { if (e.key === 'Escape' && !busy) onDone({ status: 'dismissed', failure }); };
    document.addEventListener('keydown', onKey);
    document.documentElement.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.documentElement.style.overflow = ''; };
  }, [busy, failure, onDone]);

  const pay = async (outcome) => {
    setBusy(true); setError(null);
    try {
      const res = await api.post('/api/v1/payments/mock/checkout', { razorpay_order_id: config.order_id, outcome });
      if (res.error) setFailure(res.error);        // like Razorpay: the window stays open for a retry
      else onDone({ status: 'success', response: res });
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="mockpay" role="presentation">
      <div className="mockpay__panel" role="dialog" aria-modal="true" aria-labelledby="mockpay-title" ref={panel}>
        <p className="mockpay__badge">Test mode · no real payment</p>
        <h2 id="mockpay-title">{config.name}</h2>
        <p className="mockpay__desc">{config.description}</p>
        <p className="mockpay__amount">{rupees(config.amount)}</p>
        <p className="mockpay__note">This window stands in for Razorpay while the site runs without a Razorpay account.
          Choose what the guest's payment does; the booking is then confirmed through the normal secure verification.</p>
        {failure && <p className="mockpay__msg" role="alert">Payment failed: {failure.description}. You can try again.</p>}
        {error && <p className="mockpay__msg" role="alert">{error}</p>}
        <div className="mockpay__actions">
          <button type="button" className="btn" disabled={busy} onClick={() => pay('success')} data-autofocus>
            {busy ? 'Processing…' : `Pay ${rupees(config.amount)} (test)`}
          </button>
          <button type="button" className="btn btn--ghost mockpay__fail" disabled={busy} onClick={() => pay('failure')}>Simulate failed payment</button>
          <button type="button" className="mockpay__cancel" disabled={busy} onClick={() => onDone({ status: 'dismissed', failure })}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

export function openMockCheckout(config) {
  return new Promise((resolve) => {
    const host = document.createElement('div');
    document.body.appendChild(host);
    const root = createRoot(host);
    const opener = document.activeElement;
    const done = (result) => {
      root.unmount();
      host.remove();
      opener?.focus?.();
      resolve(result);
    };
    root.render(<MockCheckout config={config} onDone={done} />);
  });
}

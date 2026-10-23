/* Razorpay Checkout loader and launcher. Only the public key id and order id
   come from our backend; the secret never reaches the browser. The checkout
   result is treated as untrusted and is always verified server-side. */

const SCRIPT_SRC = 'https://checkout.razorpay.com/v1/checkout.js';
let loading = null;

export function loadRazorpay() {
  if (window.Razorpay) return Promise.resolve(window.Razorpay);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = SCRIPT_SRC;
    s.async = true;
    s.onload = () => (window.Razorpay ? resolve(window.Razorpay) : reject(new Error('Razorpay unavailable')));
    s.onerror = () => {
      loading = null;
      s.remove();
      reject(new Error('We could not load the secure payment window. Check your connection and try again.'));
    };
    document.head.appendChild(s);
  });
  return loading;
}

/**
 * Opens checkout. Resolves with {status: 'success', response} or
 * {status: 'dismissed', failure} when the guest closes the window.
 * `failure` holds the last payment.failed error seen, if any.
 */
export async function openCheckout(config) {
  if (config.mode === 'mock') {
    // Server is in test payment mode: same flow, no Razorpay, no money.
    const { openMockCheckout } = await import('./mockCheckout');
    return openMockCheckout(config);
  }
  const Razorpay = await loadRazorpay();
  return new Promise((resolve) => {
    let lastFailure = null;
    const rzp = new Razorpay({
      key: config.key_id,
      order_id: config.order_id,
      amount: config.amount,
      currency: config.currency,
      name: config.name,
      description: config.description,
      image: window.location.origin + '/assets/logo/emblem-on-light.png',
      prefill: config.prefill,
      theme: { color: '#1F2348' },
      retry: { enabled: true },
      handler: (response) => resolve({ status: 'success', response }),
      modal: {
        confirm_close: true,
        ondismiss: () => resolve({ status: 'dismissed', failure: lastFailure }),
      },
    });
    rzp.on('payment.failed', (resp) => {
      // Razorpay keeps the window open so the guest can retry another method.
      lastFailure = resp && resp.error ? resp.error : { description: 'Payment failed' };
    });
    rzp.open();
  });
}

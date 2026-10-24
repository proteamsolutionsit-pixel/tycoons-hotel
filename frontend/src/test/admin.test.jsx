import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import AdminApp from '../admin/AdminApp';
import { ConfirmDialog, SortHeader } from '../admin/ui';

function json(status, body) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }));
}

const STAFF = {
  id: 2, email: 'staff@example.com', full_name: 'Front Desk', role: 'staff', is_active: true,
  last_login_at: null, created_at: '2026-10-01T00:00:00',
  permissions: ['dashboard.view', 'bookings.view', 'payments.view', 'submissions.view', 'submissions.manage', 'catalog.view'],
};
const DASH = {
  arrivals_today: 1, departures_today: 0, arrivals_next_7_days: 3, in_house_tonight: 2, rooms_total: 40,
  rooms_sold_tonight: 2, occupancy_tonight_pct: 5, pending_payment: 0, payment_review: 0, revenue_30d_paise: 1500000,
  refunded_30d_paise: 0, confirmed_30d: 1,
  new_submissions: { table_reservations: 0, spa_appointments: 0, enquiries: 2, applications: 0 },
  alerts: { payment_review: 0, stuck_authorized: 0, refund_pending: 0, refunded_active_booking: 0, payment_mismatch_7d: 0,
    webhook_signature_failures_7d: 0, failed_logins_24h: 0 },
};

describe('ConfirmDialog', () => {
  it('keeps a financial action disabled until the confirmation text is typed', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<ConfirmDialog title="Refund ₹15,000?" confirmLabel="Refund" confirmText="TYCAB12CD34" onConfirm={onConfirm} onCancel={() => {}}>body</ConfirmDialog>);
    const button = screen.getByRole('button', { name: 'Refund' });
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/Type/), 'TYCAB12CD3');
    expect(button).toBeDisabled();
    await user.type(screen.getByLabelText(/Type/), '4');
    expect(button).toBeEnabled();
    await user.click(button);
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(screen.getByRole('alertdialog')).toHaveAttribute('aria-modal', 'true');
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<ConfirmDialog title="Delete?" onConfirm={() => {}} onCancel={onCancel}>x</ConfirmDialog>);
    await user.keyboard('{Escape}');
    expect(onCancel).toHaveBeenCalled();
  });
});

describe('SortHeader', () => {
  it('announces sort state and toggles direction', async () => {
    const user = userEvent.setup();
    const onSort = vi.fn();
    render(<table><thead><tr><SortHeader label="Total" field="total" sort="total" order="desc" onSort={onSort} /></tr></thead></table>);
    expect(screen.getByRole('columnheader')).toHaveAttribute('aria-sort', 'descending');
    await user.click(screen.getByRole('button', { name: /Total/ }));
    expect(onSort).toHaveBeenCalledWith('total', 'asc');
  });
});

describe('Admin navigation', () => {
  it('shows only what the signed-in role may use', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, STAFF);
      if (u.includes('/dashboard')) return json(200, DASH);
      if (u.includes('/occupancy')) return json(200, { start: '2026-10-23', days: [], rooms: [] });
      return json(404, { error: { code: 'not_found', message: 'nope' } });
    });
    render(<MemoryRouter initialEntries={['/admin']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole('link', { name: 'Bookings' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Staff users' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Audit log' })).not.toBeInTheDocument();
    expect(await screen.findByText('5%')).toBeInTheDocument();        // occupancy from the API
    expect(screen.getByText('Nothing needs attention.')).toBeInTheDocument();
  });

  it('sends a signed-out user to the sign-in screen', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() => json(401, { error: { code: 'not_authenticated', message: 'Please sign in.' } }));
    render(<MemoryRouter initialEntries={['/admin/bookings']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole('heading', { name: 'Staff sign in' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Forgot password?' })).toBeInTheDocument();
  });
});

describe('Payment gateway settings', () => {
  const ADMIN = { ...STAFF, id: 1, role: 'admin', permissions: [...STAFF.permissions, 'payments.settings', 'users.manage'] };
  const CFG = {
    mode: 'mock', active: 'mock', source: 'environment', key_id: '', key_kind: null, has_key_secret: false,
    has_webhook_secret: false, secrets_readable: true, environment: 'staging', mock_allowed: true,
    webhook_url: 'https://hotel.example/api/v1/payments/webhook', updated_at: null, updated_by: null,
  };

  function mount(onPut) {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, init = {}) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, ADMIN);
      if (u.includes('/payment-settings') && init.method === 'PUT') return onPut(JSON.parse(init.body));
      if (u.includes('/payment-settings')) return json(200, CFG);
      return json(404, { error: { code: 'not_found', message: 'nope' } });
    });
    render(<MemoryRouter initialEntries={['/admin/payment-gateway']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
  }

  it('is hidden from staff', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, STAFF);
      if (u.includes('/occupancy')) return json(200, { start: '2026-10-23', days: [], rooms: [] });
      return json(200, DASH);
    });
    render(<MemoryRouter initialEntries={['/admin']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole('link', { name: 'Bookings' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Payment gateway' })).not.toBeInTheDocument();
  });

  it('asks for confirmation before switching to live keys', async () => {
    const user = userEvent.setup();
    const onPut = vi.fn((body) => json(200, { ...CFG, mode: 'razorpay', active: 'live', source: 'admin', key_id: body.key_id, key_kind: 'live', has_key_secret: true, has_webhook_secret: true }));
    mount(onPut);
    expect(await screen.findByText(/Now active: Test payments/)).toBeInTheDocument();
    await user.click(screen.getByLabelText(/Razorpay \(test or live keys\)/));
    await user.type(screen.getByLabelText('Key Id'), 'rzp_live_ZyXwVu0987654321');
    await user.type(screen.getByLabelText('Key Secret'), 'secret-value-123456');
    await user.click(screen.getByRole('button', { name: 'Generate' }));
    expect(screen.getByLabelText('Webhook secret').value).toMatch(/^[0-9a-f]{48}$/);
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(onPut).not.toHaveBeenCalled();
    const dialog = await screen.findByRole('alertdialog');
    expect(dialog).toHaveTextContent('real money');
    await user.type(screen.getByLabelText(/Type/), 'LIVE');
    await user.click(screen.getByRole('button', { name: 'Use live keys' }));
    expect(onPut).toHaveBeenCalledOnce();
    expect(onPut.mock.calls[0][0]).toMatchObject({ mode: 'razorpay', key_id: 'rzp_live_ZyXwVu0987654321', confirm_live: true });
    expect(await screen.findByText(/Now active: Razorpay LIVE/)).toBeInTheDocument();
    expect(screen.getByLabelText('Key Secret').value).toBe('');      // never echoed back
  });
});

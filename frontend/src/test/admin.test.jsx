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

describe('Audit log table', () => {
  const ADMIN = { ...STAFF, id: 1, role: 'admin', permissions: [...STAFF.permissions, 'audit.view'] };
  const entry = (id) => ({ id, occurred_at: '2026-10-26T04:00:00', actor_type: 'admin', actor_id: 1, actor_email: `user${id}@example.com`,
    action: 'auth.login', resource_type: 'admin_user', resource_id: '1', outcome: 'success', ip: '10.0.0.1', request_id: 'r', details: null });

  it('sorts, pages and exports through the server with the current filters', async () => {
    const user = userEvent.setup();
    const calls = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, ADMIN);
      if (u.includes('/audit-logs')) {
        calls.push(new URL(u, 'http://x').searchParams);
        return json(200, { items: [entry(1), entry(2)], total: 120, limit: 50, offset: 0 });
      }
      return json(404, { error: { code: 'not_found', message: 'nope' } });
    });
    render(<MemoryRouter initialEntries={['/admin/audit?outcome=failure']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    expect(await screen.findByText('user1@example.com')).toBeInTheDocument();
    expect(screen.getByText('1–50 of 120')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Export CSV' })).toHaveAttribute('href', '/api/v1/admin/audit-logs/export?outcome=failure&sort=occurred_at&order=desc');

    await user.click(screen.getByRole('button', { name: /Actor/ }));
    expect(calls.at(-1).get('sort')).toBe('actor');
    await user.click(screen.getByRole('button', { name: 'Page 3' }));
    expect(calls.at(-1).get('offset')).toBe('100');
    await user.selectOptions(screen.getByLabelText('Rows per page'), '100');
    expect(calls.at(-1).get('limit')).toBe('100');
    expect(calls.at(-1).get('offset')).toBe('0');           // new page size starts from the top
  });
});

describe('pageWindow', () => {
  it('keeps first, last and neighbours, with gaps', async () => {
    const { pageWindow } = await import('../admin/ui');
    expect(pageWindow(1, 3)).toEqual([1, 2, 3]);
    expect(pageWindow(5, 10)).toEqual([1, null, 4, 5, 6, null, 10]);
    expect(pageWindow(1, 10)).toEqual([1, 2, null, 10]);
  });
});

describe('Data tables across the admin', () => {
  const ADMIN = { ...STAFF, id: 1, role: 'admin', permissions: [...STAFF.permissions, 'users.manage', 'data.export'] };
  const mount = (path, me, handler) => {
    const calls = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, me);
      calls.push(new URL(u, 'http://x'));
      return handler(u);
    });
    render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    return calls;
  };
  const sub = (id, name) => ({ id, name, email: `${name}@x.in`, topic: 'Other', kind: 'contact', message: 'hi', status: 'new', created_at: '2026-10-26T04:00:00' });

  it('guest requests: sortable, page size, export for admins only', async () => {
    const user = userEvent.setup();
    const calls = mount('/admin/submissions?tab=enquiries', ADMIN, () => json(200, { items: [sub(1, 'amit'), sub(2, 'bina')], total: 60, limit: 25, offset: 0 }));
    expect(await screen.findByText('amit')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Export CSV' }).getAttribute('href')).toBe('/api/v1/admin/submissions/enquiries/export?sort=created_at&order=desc');
    await user.click(screen.getByRole('button', { name: /^From/ }));
    expect(calls.at(-1).searchParams.get('sort')).toBe('name');
    await user.selectOptions(screen.getByLabelText('Rows per page'), '50');
    expect(calls.at(-1).searchParams.get('limit')).toBe('50');
  });

  it('staff see no export button', async () => {
    mount('/admin/submissions?tab=enquiries', STAFF, () => json(200, { items: [sub(1, 'amit')], total: 1, limit: 25, offset: 0 }));
    expect(await screen.findByText('amit')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Export CSV' })).not.toBeInTheDocument();
  });

  it('staff users: searches and sorts in the browser', async () => {
    const user = userEvent.setup();
    const users = [
      { id: 1, email: 'zed@x.in', full_name: 'Zed Admin', role: 'admin', role_id: 1, role_name: 'Administrator', is_active: true, last_login_at: null, created_at: '2026-10-01T00:00:00' },
      { id: 2, email: 'amy@x.in', full_name: 'Amy Desk', role: 'staff', role_id: 2, role_name: 'Front desk', is_active: true, last_login_at: null, created_at: '2026-10-01T00:00:00' },
    ];
    mount('/admin/users', ADMIN, (u) => json(200, u.includes('/roles') ? [] : users));
    await screen.findByText('Amy Desk');
    const names = () => screen.getAllByRole('row').slice(1).map((r) => r.cells[0].textContent.replace(' (you)', ''));
    expect(names()).toEqual(['Amy Desk', 'Zed Admin']);
    await user.click(screen.getByRole('button', { name: /^Name/ }));      // already ascending -> descending
    expect(names()).toEqual(['Zed Admin', 'Amy Desk']);
    await user.type(screen.getByPlaceholderText('Name, email or role'), 'front desk');
    expect(await screen.findByText('1 total')).toBeInTheDocument();
    expect(names()).toEqual(['Amy Desk']);
  });
});

describe('csvCell', () => {
  it('quotes and defuses formulas', async () => {
    const { csvCell, toCsv } = await import('../utils/csv');
    expect(csvCell('=SUM(A1)')).toBe("'=SUM(A1)");
    expect(csvCell('a,b')).toBe('"a,b"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell(true)).toBe('yes');
    expect(csvCell(null)).toBe('');
    expect(toCsv(['a', 'b'], [[1, 'x']])).toBe('a,b\r\n1,x');
  });
});

describe('Roles & access', () => {
  const ADMIN = { ...STAFF, id: 1, role: 'admin', permissions: [...STAFF.permissions, 'users.manage', 'roles.manage'] };
  const CATALOGUE = [
    { key: 'payments.view', group: 'Operations', label: 'View payments', description: 'd', implies: [] },
    { key: 'bookings.view', group: 'Operations', label: 'View bookings & occupancy', description: 'd', implies: [] },
    { key: 'payments.refund', group: 'Operations', label: 'Issue refunds', description: 'd', implies: ['bookings.view', 'payments.view'] },
    { key: 'audit.view', group: 'Administration', label: 'Audit log', description: 'd', implies: [] },
  ];
  const ROLES = [
    { id: 1, key: 'administrator', name: 'Administrator', description: 'All', permissions: CATALOGUE.map((p) => p.key), is_system: true, user_count: 1, updated_at: '2026-10-26T00:00:00' },
    { id: 2, key: 'front_desk', name: 'Front desk', description: 'Desk', permissions: ['bookings.view'], is_system: false, user_count: 3, updated_at: '2026-10-26T00:00:00' },
  ];

  it('creates a role; ticking an action locks in what it needs', async () => {
    const user = userEvent.setup();
    const posted = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((url, init = {}) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, ADMIN);
      if (u.endsWith('/roles/permissions')) return json(200, CATALOGUE);
      if (u.endsWith('/roles') && init.method === 'POST') { posted.push(JSON.parse(init.body)); return json(201, { ...ROLES[1], id: 3 }); }
      if (u.endsWith('/roles')) return json(200, ROLES);
      return json(404, { error: { code: 'not_found', message: 'nope' } });
    });
    render(<MemoryRouter initialEntries={['/admin/roles']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    expect(await screen.findByText('Full access')).toBeInTheDocument();
    expect(screen.getByText('1 of 4')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Roles & access' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'New role' }));
    await user.type(screen.getByLabelText('Role name'), 'Finance');
    await user.click(screen.getByRole('checkbox', { name: /Issue refunds/ }));
    const view = screen.getByRole('checkbox', { name: /View payments/ });
    expect(view).toBeChecked();
    expect(view).toBeDisabled();                       // required by "Issue refunds"
    expect(screen.getByRole('checkbox', { name: /Audit log/ })).not.toBeChecked();
    await user.click(screen.getByRole('button', { name: 'Create role' }));
    expect(posted[0].name).toBe('Finance');
    expect(new Set(posted[0].permissions)).toEqual(new Set(['payments.refund', 'bookings.view', 'payments.view']));
  });

  it('shows the Administrator role read-only', async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, 'fetch').mockImplementation((url) => {
      const u = String(url);
      if (u.includes('/auth/me')) return json(200, ADMIN);
      if (u.endsWith('/roles/permissions')) return json(200, CATALOGUE);
      return json(200, ROLES);
    });
    render(<MemoryRouter initialEntries={['/admin/roles']}><Routes><Route path="/admin/*" element={<AdminApp />} /></Routes></MemoryRouter>);
    await user.click(await screen.findByText('Administrator'));
    expect(screen.getByLabelText('Role name')).toBeDisabled();
    expect(screen.queryByRole('button', { name: /Save role/ })).not.toBeInTheDocument();
  });
});

import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../../services/api';
import { dateTime, guestsLabel, longDate, rupees } from '../../utils/format';
import { Can, useAuth } from '../auth';
import { Badge, ConfirmDialog, Drawer, PageTitle, Pager, SearchBox, SortHeader, StateRow, useAdminList, useToast } from '../ui';

const STATUSES = ['', 'pending_payment', 'confirmed', 'payment_review', 'cancelled', 'expired'];

export default function Bookings() {
  const [params, setParams] = useSearchParams();
  const { id } = useParams();
  const navigate = useNavigate();
  const status = params.get('status') || '';
  const q = params.get('q') || '';
  const sort = params.get('sort') || 'created_at';
  const order = params.get('order') || 'desc';
  const offset = Number(params.get('offset') || 0);
  const list = useAdminList('/api/v1/admin/bookings', {
    status, q, sort, order, offset, limit: 25,
    check_in_from: params.get('from') || undefined, check_in_to: params.get('to') || undefined,
  });
  const update = (changes) => {
    const p = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!('offset' in changes)) p.delete('offset');
    setParams(p);
  };
  const open = (b) => navigate(`/admin/bookings/${b.id}?${params}`);
  const sortProps = { sort, order, onSort: (f, o) => update({ sort: f, order: o }) };

  return (
    <>
      <PageTitle title="Bookings" subtitle={list.data ? `${list.data.total} matching` : undefined} />
      <div className="adm-toolbar" role="search">
        <SearchBox value={q} onChange={(v) => update({ q: v })} placeholder="Reference, name, email or phone" />
        <select className="adm-input" value={status} onChange={(e) => update({ status: e.target.value })} aria-label="Status">
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'All statuses'}</option>)}
        </select>
        <label className="adm-inline">Check-in from <input className="adm-input" type="date" value={params.get('from') || ''} onChange={(e) => update({ from: e.target.value })} /></label>
        <label className="adm-inline">to <input className="adm-input" type="date" value={params.get('to') || ''} onChange={(e) => update({ to: e.target.value })} /></label>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr>
            <SortHeader label="Reference" field="reference" {...sortProps} />
            <SortHeader label="Guest" field="guest" {...sortProps} />
            <th>Room</th>
            <SortHeader label="Stay" field="check_in" {...sortProps} />
            <SortHeader label="Total" field="total" {...sortProps} />
            <SortHeader label="Status" field="status" {...sortProps} />
            <th>Payment</th>
            <SortHeader label="Created" field="created_at" {...sortProps} />
          </tr></thead>
          <tbody>
            <StateRow state={list} cols={8} empty="No bookings match these filters." />
            {list.data?.items.map((b) => (
              <tr key={b.id} className="adm-row-link" tabIndex={0} onClick={() => open(b)} onKeyDown={(e) => { if (e.key === 'Enter') open(b); }}>
                <td className="adm-mono">{b.reference}</td>
                <td>{b.guest_name}<br /><span className="adm-muted">{b.guest_email}</span></td>
                <td>{b.room_type_name}</td>
                <td>{longDate(b.check_in)} → {longDate(b.check_out)}<br /><span className="adm-muted">{b.nights} nt · {guestsLabel(b.adults, b.children)}</span></td>
                <td className="adm-num">{rupees(b.total_paise)}</td>
                <td><Badge value={b.status} /></td>
                <td><Badge value={b.payment_status} /></td>
                <td className="adm-muted">{dateTime(b.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} onChange={(o) => update({ offset: String(o) })} />
      {id && <BookingDetail id={id} onClose={() => navigate(`/admin/bookings?${params}`)} onChanged={list.reload} />}
    </>
  );
}

function BookingDetail({ id, onClose, onChanged }) {
  const { can, handleError } = useAuth();
  const toast = useToast();
  const detail = useAdminList(`/api/v1/admin/bookings/${id}`);
  const [dialog, setDialog] = useState(null); // 'cancel' | 'refund' | 'review'
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const b = detail.data;

  const run = async (fn, ok) => {
    setBusy(true);
    try { await fn(); toast(ok); setDialog(null); setReason(''); detail.reload(); onChanged(); }
    catch (err) { handleError(err); toast(err.message, 'error'); }
    finally { setBusy(false); }
  };
  const captured = b?.payments.find((p) => p.status === 'captured');
  const closed = b && ['cancelled', 'expired'].includes(b.status);
  const amountText = captured ? rupees(captured.amount_paise) : '';

  return (
    <Drawer title={b ? `Booking ${b.reference}` : 'Booking'} onClose={onClose} wide>
      {detail.error && <p className="adm-error" role="alert">{detail.error.message}</p>}
      {!b && !detail.error && <span className="adm-skeleton adm-skeleton--block" />}
      {b && (
        <>
          <div className="adm-detail-head">
            <Badge value={b.status} />
            <span className="adm-detail-head__total">{rupees(b.total_paise)}</span>
            {b.cancel_reason && <span className="adm-muted">Cancelled: {b.cancel_reason}</span>}
          </div>

          <div className="adm-detail-grid">
            <section>
              <h3>Guest</h3>
              <dl className="adm-dl">
                <dt>Name</dt><dd>{b.guest_name}</dd>
                <dt>Email</dt><dd><a href={`mailto:${b.guest_email}`}>{b.guest_email}</a></dd>
                <dt>Phone</dt><dd><a href={`tel:${b.guest_phone}`}>{b.guest_phone}</a></dd>
                {b.special_requests && (<><dt>Requests</dt><dd>{b.special_requests}</dd></>)}
              </dl>
            </section>
            <section>
              <h3>Stay</h3>
              <dl className="adm-dl">
                <dt>Room</dt><dd>{b.room_type_name}</dd>
                <dt>Dates</dt><dd>{longDate(b.check_in)} → {longDate(b.check_out)} ({b.nights} nights)</dd>
                <dt>Guests</dt><dd>{guestsLabel(b.adults, b.children)}</dd>
                <dt>Price</dt><dd>{rupees(b.nightly_rate_paise)} × {b.nights} = {rupees(b.subtotal_paise)}{b.tax_paise ? ` + tax ${rupees(b.tax_paise)} (${Number(b.tax_percent)}%)` : ''}</dd>
              </dl>
            </section>
            <section>
              <h3>Timeline</h3>
              <dl className="adm-dl">
                <dt>Created</dt><dd>{dateTime(b.created_at)}</dd>
                {b.hold_expires_at && (<><dt>Hold until</dt><dd>{dateTime(b.hold_expires_at)}</dd></>)}
                {b.confirmed_at && (<><dt>Confirmed</dt><dd>{dateTime(b.confirmed_at)}</dd></>)}
                {b.cancelled_at && (<><dt>Cancelled</dt><dd>{dateTime(b.cancelled_at)}</dd></>)}
              </dl>
            </section>
            <section>
              <h3>Terms accepted</h3>
              {b.terms_accepted_at ? (
                <dl className="adm-dl">
                  <dt>Version</dt><dd>{b.terms_version || '—'}</dd>
                  <dt>Accepted</dt><dd>{dateTime(b.terms_accepted_at)}</dd>
                  <dt>Policy</dt><dd className="adm-pre">{b.cancellation_policy || '—'}</dd>
                </dl>
              ) : <p className="adm-muted">Not recorded (booking made before terms were recorded).</p>}
            </section>
          </div>

          <section className="adm-section">
            <h3>Payments</h3>
            <div className="adm-table-wrap">
              <table className="adm-table adm-table--compact">
                <thead><tr><th>Order</th><th>Payment</th><th>Amount</th><th>Status</th><th>Method</th><th><span className="visually-hidden">Actions</span></th></tr></thead>
                <tbody>
                  {b.payments.length === 0 && <tr><td colSpan={6} className="adm-muted">No payment order.</td></tr>}
                  {b.payments.map((p) => (
                    <tr key={p.id}>
                      <td className="adm-mono">{p.razorpay_order_id}</td>
                      <td className="adm-mono">{p.razorpay_payment_id || '—'}{p.error_description && <><br /><span className="adm-error">{p.error_description}</span></>}{p.razorpay_refund_id && <><br /><span className="adm-muted">Refund {p.razorpay_refund_id}</span></>}</td>
                      <td className="adm-num">{rupees(p.amount_paise)}</td>
                      <td><Badge value={p.status} />{p.signature_verified && <><br /><small className="adm-muted">signature verified</small></>}</td>
                      <td>{p.method || '—'}</td>
                      <td><Can permission="payments.reconcile">
                        <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" disabled={busy}
                          onClick={() => run(() => api.post(`/api/v1/admin/payments/${p.id}/reconcile`), 'Checked with Razorpay.')}>Reconcile</button>
                      </Can></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {b.events.length > 0 && (
            <section className="adm-section">
              <h3>Payment log</h3>
              <ol className="adm-timeline">
                {b.events.map((e) => (
                  <li key={e.id}><span className="adm-muted">{dateTime(e.created_at)}</span> <strong>{e.event_type}</strong> <span className="adm-muted">via {e.source}</span>{e.result && <> — {e.result}</>}</li>
                ))}
              </ol>
            </section>
          )}

          {!closed && can('bookings.manage') && (
            <section className="adm-section adm-actions-panel">
              <h3>Actions</h3>
              <div className="adm-field">
                <label htmlFor="b-reason">Reason (recorded in the audit log)</label>
                <input id="b-reason" className="adm-input" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Guest asked to cancel by phone" />
              </div>
              <div className="adm-btn-row">
                {b.status === 'payment_review' && (
                  <button type="button" className="adm-btn" disabled={reason.trim().length < 3} onClick={() => setDialog('review')}>Confirm booking (room found)</button>
                )}
                {captured && can('payments.refund') && (
                  <button type="button" className="adm-btn adm-btn--danger" disabled={reason.trim().length < 3} onClick={() => setDialog('refund')}>Cancel and refund {amountText}</button>
                )}
                <button type="button" className="adm-btn adm-btn--ghost" disabled={reason.trim().length < 3} onClick={() => setDialog('cancel')}>
                  {captured ? 'Cancel without refund' : 'Cancel booking'}
                </button>
              </div>
              {reason.trim().length < 3 && <small className="adm-muted">Enter a reason to enable these actions.</small>}
            </section>
          )}
        </>
      )}

      {dialog === 'refund' && b && captured && (
        <ConfirmDialog title={`Refund ${amountText} and cancel ${b.reference}?`} danger confirmLabel={`Refund ${amountText}`}
          confirmText={b.reference} busy={busy} onCancel={() => setDialog(null)}
          onConfirm={() => run(() => api.post(`/api/v1/admin/bookings/${b.id}/cancel`, { reason, refund: true, confirm_refund_paise: captured.amount_paise }),
            `Refund of ${amountText} issued and booking cancelled.`)}>
          <p>The full payment of <strong>{amountText}</strong> to {b.guest_name} is refunded through Razorpay (normal speed, usually 5–7 working days), and the room is released.</p>
          <p className="adm-muted">This cannot be undone.</p>
        </ConfirmDialog>
      )}
      {dialog === 'cancel' && b && (
        <ConfirmDialog title={`Cancel ${b.reference}?`} danger confirmLabel="Cancel booking" busy={busy} onCancel={() => setDialog(null)}
          onConfirm={() => run(() => api.post(`/api/v1/admin/bookings/${b.id}/cancel`, { reason, refund: false }), 'Booking cancelled.')}>
          {captured
            ? <p><strong>No refund will be issued.</strong> The guest paid {amountText}; this cancels the booking and keeps the payment. This is recorded in the audit log.</p>
            : <p>The room is released. The guest has not paid.</p>}
        </ConfirmDialog>
      )}
      {dialog === 'review' && b && (
        <ConfirmDialog title={`Confirm ${b.reference}?`} confirmLabel="Confirm booking" busy={busy} onCancel={() => setDialog(null)}
          onConfirm={() => run(() => api.post(`/api/v1/admin/bookings/${b.id}/confirm`, { note: reason }), 'Booking confirmed; the guest has been emailed.')}>
          <p>Use this once a {b.room_type_name} is free for these dates (for example after raising inventory). The system checks availability again before confirming.</p>
        </ConfirmDialog>
      )}
    </Drawer>
  );
}

import { useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api } from '../../services/api';
import { dateTime, guestsLabel, longDate, rupees } from '../../utils/format';
import { useAuth } from '../auth';
import { Badge, Drawer, Notice, PageTitle, Pager, SearchBox, StateRow, useAdminList } from '../ui';

const STATUSES = ['', 'pending_payment', 'confirmed', 'payment_review', 'cancelled', 'expired'];

export default function Bookings() {
  const [params, setParams] = useSearchParams();
  const { id } = useParams();
  const navigate = useNavigate();
  const status = params.get('status') || '';
  const q = params.get('q') || '';
  const offset = Number(params.get('offset') || 0);
  const list = useAdminList('/api/admin/bookings', { status, q, offset, limit: 25,
    check_in_from: params.get('from') || undefined, check_in_to: params.get('to') || undefined });
  const update = (k, v) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); if (k !== 'offset') p.delete('offset'); setParams(p); };

  return (
    <>
      <PageTitle title="Bookings" />
      <div className="adm-toolbar">
        <SearchBox value={q} onChange={(v) => update('q', v)} placeholder="Reference, name, email or phone" />
        <select className="adm-input" value={status} onChange={(e) => update('status', e.target.value)} aria-label="Status">
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'All statuses'}</option>)}
        </select>
        <label className="adm-muted">Check-in from <input className="adm-input" type="date" value={params.get('from') || ''} onChange={(e) => update('from', e.target.value)} /></label>
        <label className="adm-muted">to <input className="adm-input" type="date" value={params.get('to') || ''} onChange={(e) => update('to', e.target.value)} /></label>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr><th>Reference</th><th>Guest</th><th>Room</th><th>Stay</th><th>Total</th><th>Status</th><th>Payment</th><th>Created</th></tr></thead>
          <tbody>
            <StateRow state={list} cols={8} empty="No bookings match." />
            {list.data?.items.map((b) => (
              <tr key={b.id} className="adm-row-link" tabIndex={0} onClick={() => navigate(`/admin/bookings/${b.id}?${params}`)}
                onKeyDown={(e) => { if (e.key === 'Enter') navigate(`/admin/bookings/${b.id}?${params}`); }}>
                <td className="adm-mono">{b.reference}</td>
                <td>{b.guest_name}<br /><span className="adm-muted">{b.guest_email}</span></td>
                <td>{b.room_type_name}</td>
                <td>{longDate(b.check_in)} → {longDate(b.check_out)}<br /><span className="adm-muted">{b.nights} nt · {guestsLabel(b.adults, b.children)}</span></td>
                <td>{rupees(b.total_paise)}</td>
                <td><Badge value={b.status} /></td>
                <td><Badge value={b.payment_status} /></td>
                <td className="adm-muted">{dateTime(b.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} onChange={(o) => update('offset', String(o))} />
      {id && <BookingDetail id={id} onClose={() => navigate(`/admin/bookings?${params}`)} onChanged={list.reload} />}
    </>
  );
}

function BookingDetail({ id, onClose, onChanged }) {
  const { isAdmin, handleError } = useAuth();
  const detail = useAdminList(`/api/admin/bookings/${id}`);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState('');
  const [refund, setRefund] = useState(true);
  const b = detail.data;

  const act = async (fn, ok) => {
    setBusy(true); setNotice(null);
    try { await fn(); setNotice({ type: 'success', message: ok }); detail.reload(); onChanged(); }
    catch (err) { handleError(err); setNotice({ type: 'error', message: err.message }); }
    finally { setBusy(false); }
  };
  const captured = b?.payments.some((p) => p.status === 'captured');
  const closed = b && ['cancelled', 'expired'].includes(b.status);

  return (
    <Drawer title={b ? `Booking ${b.reference}` : 'Booking'} onClose={onClose} wide>
      {detail.error && <p className="adm-error">{detail.error.message}</p>}
      {!b && !detail.error && <p className="adm-muted">Loading…</p>}
      {b && (
        <>
          <Notice notice={notice} onClose={() => setNotice(null)} />
          <dl className="adm-dl">
            <dt>Status</dt><dd><Badge value={b.status} /> {b.cancel_reason && <span className="adm-muted">— {b.cancel_reason}</span>}</dd>
            <dt>Guest</dt><dd>{b.guest_name} · <a href={`mailto:${b.guest_email}`}>{b.guest_email}</a> · <a href={`tel:${b.guest_phone}`}>{b.guest_phone}</a></dd>
            <dt>Room</dt><dd>{b.room_type_name}</dd>
            <dt>Stay</dt><dd>{longDate(b.check_in)} → {longDate(b.check_out)} ({b.nights} nights), {guestsLabel(b.adults, b.children)}</dd>
            <dt>Price</dt><dd>{rupees(b.nightly_rate_paise)} × {b.nights} = {rupees(b.subtotal_paise)}{b.tax_paise ? ` + tax ${rupees(b.tax_paise)} (${Number(b.tax_percent)}%)` : ''} = <strong>{rupees(b.total_paise)}</strong></dd>
            {b.special_requests && (<><dt>Requests</dt><dd>{b.special_requests}</dd></>)}
            <dt>Created</dt><dd>{dateTime(b.created_at)}</dd>
            {b.hold_expires_at && (<><dt>Hold until</dt><dd>{dateTime(b.hold_expires_at)}</dd></>)}
            {b.confirmed_at && (<><dt>Confirmed</dt><dd>{dateTime(b.confirmed_at)}</dd></>)}
            {b.cancelled_at && (<><dt>Cancelled</dt><dd>{dateTime(b.cancelled_at)}</dd></>)}
          </dl>

          <div className="adm-section">
            <h3>Payments</h3>
            <div className="adm-table-wrap">
              <table className="adm-table">
                <thead><tr><th>Order</th><th>Payment</th><th>Amount</th><th>Status</th><th>Method</th><th /></tr></thead>
                <tbody>
                  {b.payments.length === 0 && <tr><td colSpan={6} className="adm-muted">No payment order.</td></tr>}
                  {b.payments.map((p) => (
                    <tr key={p.id}>
                      <td className="adm-mono">{p.razorpay_order_id}</td>
                      <td className="adm-mono">{p.razorpay_payment_id || '—'}{p.error_description && <><br /><span className="adm-error">{p.error_description}</span></>}</td>
                      <td>{rupees(p.amount_paise)}</td>
                      <td><Badge value={p.status} />{p.signature_verified && <><br /><span className="adm-muted">signature verified</span></>}</td>
                      <td>{p.method || '—'}</td>
                      <td>{isAdmin && <button type="button" className="adm-btn adm-btn--ghost" disabled={busy}
                        onClick={() => act(() => api.post(`/api/admin/payments/${p.id}/reconcile`), 'Checked with Razorpay.')}>Reconcile</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {b.events.length > 0 && (
            <div className="adm-section">
              <h3>Payment log</h3>
              <div className="adm-table-wrap">
                <table className="adm-table">
                  <thead><tr><th>When</th><th>Source</th><th>Event</th><th>Result</th></tr></thead>
                  <tbody>
                    {b.events.map((e) => (
                      <tr key={e.id}><td className="adm-muted">{dateTime(e.created_at)}</td><td>{e.source}</td><td className="adm-mono">{e.event_type}</td><td>{e.result}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {isAdmin && !closed && (
            <div className="adm-section">
              <h3>Cancel booking</h3>
              <form className="adm-form" onSubmit={(e) => {
                e.preventDefault();
                if (!window.confirm(`Cancel ${b.reference}${captured && refund ? ' and refund ' + rupees(b.total_paise) : ''}?`)) return;
                act(() => api.post(`/api/admin/bookings/${b.id}/cancel`, { reason, refund: captured && refund }), 'Booking cancelled.');
              }}>
                <div className="adm-field adm-field--wide"><label htmlFor="c-reason">Reason</label>
                  <input id="c-reason" className="adm-input" required minLength={3} maxLength={255} value={reason} onChange={(e) => setReason(e.target.value)} /></div>
                {captured && (
                  <div className="adm-field adm-field--check adm-field--wide">
                    <label htmlFor="c-refund">Refund {rupees(b.total_paise)} to the guest through Razorpay</label>
                    <input id="c-refund" type="checkbox" checked={refund} onChange={(e) => setRefund(e.target.checked)} />
                  </div>
                )}
                <div className="adm-form__actions"><button className="adm-btn adm-btn--danger" type="submit" disabled={busy}>Cancel booking</button></div>
              </form>
            </div>
          )}
        </>
      )}
    </Drawer>
  );
}

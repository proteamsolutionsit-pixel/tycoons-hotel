import { Link, useSearchParams } from 'react-router-dom';
import { dateTime, rupees } from '../../utils/format';
import { Badge, PageTitle, Pager, SearchBox, StateRow, useAdminList } from '../ui';

const STATUSES = ['', 'created', 'authorized', 'captured', 'failed', 'refund_pending', 'refunded'];

export default function Payments() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || '';
  const q = params.get('q') || '';
  const offset = Number(params.get('offset') || 0);
  const list = useAdminList('/api/admin/payments', { status, q, offset, limit: 25 });
  const update = (k, v) => { const p = new URLSearchParams(params); if (v) p.set(k, v); else p.delete(k); if (k !== 'offset') p.delete('offset'); setParams(p); };

  return (
    <>
      <PageTitle title="Payments" />
      <div className="adm-toolbar">
        <SearchBox value={q} onChange={(v) => update('q', v)} placeholder="Order / payment id, reference or guest" />
        <select className="adm-input" value={status} onChange={(e) => update('status', e.target.value)} aria-label="Status">
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'All statuses'}</option>)}
        </select>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr><th>Booking</th><th>Guest</th><th>Razorpay order</th><th>Payment</th><th>Amount</th><th>Status</th><th>Captured</th></tr></thead>
          <tbody>
            <StateRow state={list} cols={7} empty="No payments match." />
            {list.data?.items.map((p) => (
              <tr key={p.id}>
                <td className="adm-mono"><Link to={`/admin/bookings?q=${p.booking_reference}`}>{p.booking_reference}</Link></td>
                <td>{p.guest_name}</td>
                <td className="adm-mono">{p.razorpay_order_id}</td>
                <td className="adm-mono">{p.razorpay_payment_id || '—'}</td>
                <td>{rupees(p.amount_paise)}</td>
                <td><Badge value={p.status} /></td>
                <td className="adm-muted">{dateTime(p.captured_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} onChange={(o) => update('offset', String(o))} />
    </>
  );
}

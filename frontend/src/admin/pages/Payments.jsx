import { Link, useSearchParams } from 'react-router-dom';
import { dateTime, rupees } from '../../utils/format';
import { Badge, ExportButton, PAGE_SIZES, PageTitle, Pager, SearchBox, SortHeader, StateRow, useAdminList } from '../ui';

const STATUSES = ['', 'created', 'authorized', 'captured', 'failed', 'refund_pending', 'refunded'];

export default function Payments() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') || '';
  const q = params.get('q') || '';
  const sort = params.get('sort') || 'created_at';
  const order = params.get('order') || 'desc';
  const offset = Number(params.get('offset') || 0);
  const limit = PAGE_SIZES.includes(Number(params.get('limit'))) ? Number(params.get('limit')) : 25;
  const filters = { status, q, sort, order };
  const list = useAdminList('/api/v1/admin/payments', { ...filters, offset, limit });
  const update = (changes) => {
    const p = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? p.set(k, v) : p.delete(k)));
    if (!('offset' in changes)) p.delete('offset');
    setParams(p);
  };
  const sortProps = { sort, order, onSort: (f, o) => update({ sort: f, order: o }) };

  return (
    <>
      <PageTitle title="Payments" subtitle="Razorpay orders, captures and refunds. No card details are stored.">
        <ExportButton path="/api/v1/admin/payments/export" query={filters} />
      </PageTitle>
      <div className="adm-toolbar" role="search">
        <SearchBox value={q} onChange={(v) => update({ q: v })} placeholder="Order / payment id, reference or guest" />
        <select className="adm-input" value={status} onChange={(e) => update({ status: e.target.value })} aria-label="Status">
          {STATUSES.map((s) => <option key={s} value={s}>{s ? s.replace(/_/g, ' ') : 'All statuses'}</option>)}
        </select>
      </div>
      <div className="adm-table-wrap">
        <table className="adm-table">
          <thead><tr>
            <SortHeader label="Booking" field="reference" {...sortProps} />
            <SortHeader label="Guest" field="guest" {...sortProps} />
            <th>Razorpay order</th><th>Payment / refund</th>
            <SortHeader label="Amount" field="amount" {...sortProps} />
            <SortHeader label="Status" field="status" {...sortProps} />
            <SortHeader label="Captured" field="captured_at" {...sortProps} />
            <SortHeader label="Created" field="created_at" {...sortProps} />
          </tr></thead>
          <tbody>
            <StateRow state={list} cols={8} empty="No payments match these filters." />
            {list.data?.items.map((p) => (
              <tr key={p.id}>
                <td className="adm-mono"><Link to={`/admin/bookings?q=${p.booking_reference}`}>{p.booking_reference}</Link></td>
                <td>{p.guest_name}</td>
                <td className="adm-mono">{p.razorpay_order_id}</td>
                <td className="adm-mono">{p.razorpay_payment_id || '—'}{p.razorpay_refund_id && <><br /><span className="adm-muted">{p.razorpay_refund_id}</span></>}</td>
                <td className="adm-num">{rupees(p.amount_paise)}</td>
                <td><Badge value={p.status} /></td>
                <td className="adm-muted">{dateTime(p.captured_at)}</td>
                <td className="adm-muted">{dateTime(p.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={list.data} limits={PAGE_SIZES} onChange={(o) => update({ offset: String(o) })} onLimit={(n) => update({ limit: String(n) })} />
    </>
  );
}

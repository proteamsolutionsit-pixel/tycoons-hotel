/* Dashboard: every figure comes from GET /admin/dashboard and /admin/occupancy
   for the signed-in user's permissions. Nothing is estimated or hardcoded. */
import { Link } from 'react-router-dom';
import { hotelToday, rupees } from '../../utils/format';
import { useAuth } from '../auth';
import { IconAlert, IconCheck, IconRefresh } from '../icons';
import { OccupancyGrid } from './Occupancy';
import { PageTitle, StatCard, useAdminList } from '../ui';

const ALERTS = [
  ['payment_review', 'Payments awaiting review', 'Money captured after the hold lapsed and the room was gone. Rehouse or refund.', '/admin/bookings?status=payment_review'],
  ['refunded_active_booking', 'Refunded but still booked', 'Refunded in Razorpay while the stay is still confirmed. Cancel the booking or re-charge.', '/admin/payments?status=refunded'],
  ['stuck_authorized', 'Authorised, not captured (30 min+)', 'Open the booking and use Reconcile.', '/admin/payments?status=authorized'],
  ['refund_pending', 'Refunds in progress', 'Razorpay has not reported these refunds as processed yet.', '/admin/payments?status=refund_pending'],
  ['payment_mismatch_7d', 'Payment mismatches (7 days)', 'Amount or order did not match, or a webhook for an unknown order.', '/admin/audit'],
  ['webhook_signature_failures_7d', 'Rejected webhook signatures (7 days)', 'Requests to the webhook URL with an invalid signature.', '/admin/audit?action=security.webhook'],
  ['failed_logins_24h', 'Failed staff sign-ins (24 h)', 'Repeated failures can mean password guessing.', '/admin/audit?action=auth.login_failed'],
];

export default function Dashboard() {
  const { can } = useAuth();
  const d = useAdminList('/api/v1/admin/dashboard');
  const occ = useAdminList('/api/v1/admin/occupancy', { start: hotelToday(), days: 7 });
  const v = d.data;
  const active = v ? ALERTS.filter(([k]) => v.alerts[k] > 0) : [];

  return (
    <>
      <PageTitle title="Dashboard" subtitle="Today at The Tycoons Hotel">
        <button type="button" className="adm-btn adm-btn--ghost adm-btn--sm" onClick={() => { d.reload(); occ.reload(); }}>
          <IconRefresh width={16} height={16} />Refresh
        </button>
      </PageTitle>
      {d.error && <div className="adm-notice adm-notice--error" role="alert"><IconAlert /><span>{d.error.message}</span></div>}

      <section aria-label="Key figures" className="adm-stats">
        {!v && !d.error && Array.from({ length: 6 }, (_, i) => <div className="adm-stat" key={i}><span className="adm-skeleton" /></div>)}
        {v && (
          <>
            <StatCard label="Occupancy tonight" value={`${v.occupancy_tonight_pct}%`} hint={`${v.rooms_sold_tonight} of ${v.rooms_total} rooms sold`} />
            <StatCard label="Arrivals today" value={v.arrivals_today} hint={`${v.arrivals_next_7_days} in the next 7 days`} LinkComp={Link} to="/admin/bookings?status=confirmed&sort=check_in&order=asc" />
            <StatCard label="Departures today" value={v.departures_today} hint={`${v.in_house_tonight} guests in house tonight`} />
            <StatCard label="Awaiting payment" value={v.pending_payment} hint="Rooms on hold right now" LinkComp={Link} to="/admin/bookings?status=pending_payment" />
            {can('payments.view') && <StatCard label="Captured, 30 days" value={rupees(v.revenue_30d_paise)} hint={`${v.confirmed_30d} bookings confirmed`} LinkComp={Link} to="/admin/payments?status=captured" />}
            {can('payments.view') && <StatCard label="Refunded, 30 days" value={rupees(v.refunded_30d_paise)} hint="Processed refunds" LinkComp={Link} to="/admin/payments?status=refunded" />}
          </>
        )}
      </section>

      <div className="adm-grid-2">
        <section className="adm-panel" aria-labelledby="alerts-title">
          <h2 id="alerts-title">Needs attention</h2>
          {v && !active.length && <p className="adm-allclear"><IconCheck />Nothing needs attention.</p>}
          <ul className="adm-alerts">
            {active.map(([k, title, text, to]) => (
              <li key={k}>
                <Link to={to}>
                  <span className="adm-alerts__count">{v.alerts[k]}</span>
                  <span><strong>{title}</strong><small>{text}</small></span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
        <section className="adm-panel" aria-labelledby="req-title">
          <h2 id="req-title">New guest requests</h2>
          {v && (
            <ul className="adm-reqs">
              {[['table_reservations', 'Table reservations', 'table-reservations'], ['spa_appointments', 'Spa appointments', 'spa-appointments'],
                ['enquiries', 'Enquiries', 'enquiries'], ['applications', 'Job applications', 'applications']].map(([k, label, tab]) => (
                <li key={k}><Link to={`/admin/submissions?tab=${tab}`}><span>{label}</span><span className="adm-reqs__n">{v.new_submissions[k]}</span></Link></li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="adm-panel" aria-labelledby="occ-title">
        <div className="adm-panel__head">
          <h2 id="occ-title">Rooms sold, next 7 nights</h2>
          <Link to="/admin/occupancy" className="adm-link">Open calendar</Link>
        </div>
        <OccupancyGrid state={occ} />
      </section>
    </>
  );
}

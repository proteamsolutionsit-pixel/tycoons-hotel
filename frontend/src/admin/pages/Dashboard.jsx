import { Link } from 'react-router-dom';
import { rupees } from '../../utils/format';
import { PageTitle, useAdminList } from '../ui';

export default function Dashboard() {
  const d = useAdminList('/api/admin/dashboard');
  const v = d.data;
  const card = (value, label, to, alert) => (
    <Link to={to} className={'adm-card' + (alert ? ' adm-card--alert' : '')} style={{ color: 'inherit' }}>
      <div className="adm-card__value">{value}</div>
      <div className="adm-card__label">{label}</div>
    </Link>
  );
  return (
    <>
      <PageTitle title="Dashboard" />
      {d.error && <p className="adm-error">{d.error.message}</p>}
      {v && (
        <>
          <div className="adm-cards">
            {card(v.arrivals_today, 'Arrivals today', '/admin/bookings?status=confirmed')}
            {card(v.arrivals_next_7_days, 'Arrivals next 7 days', '/admin/bookings?status=confirmed')}
            {card(v.in_house_tonight, 'In house tonight', '/admin/bookings?status=confirmed')}
            {card(v.pending_payment, 'Awaiting payment', '/admin/bookings?status=pending_payment')}
            {card(v.payment_review, 'Payments needing review', '/admin/bookings?status=payment_review', v.payment_review > 0)}
            {card(rupees(v.revenue_30d_paise), 'Captured, last 30 days', '/admin/payments?status=captured')}
            {card(v.confirmed_30d, 'Bookings confirmed, 30 days', '/admin/bookings?status=confirmed')}
          </div>
          <h2>New requests</h2>
          <div className="adm-cards">
            {card(v.new_submissions.table_reservations, 'Table reservations', '/admin/submissions?tab=table-reservations')}
            {card(v.new_submissions.spa_appointments, 'Spa appointments', '/admin/submissions?tab=spa-appointments')}
            {card(v.new_submissions.enquiries, 'Enquiries', '/admin/submissions?tab=enquiries')}
            {card(v.new_submissions.applications, 'Job applications', '/admin/submissions?tab=applications')}
          </div>
        </>
      )}
    </>
  );
}

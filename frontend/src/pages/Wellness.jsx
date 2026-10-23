import { Link } from 'react-router-dom';
import { SpaAppointmentForm } from '../components/forms/SiteForms';
import { CardGrid, DetailsStrip, PageHero, StateMessage } from '../components/Sections';
import { useSite } from '../context/SiteContext';
import { useApi } from '../hooks/useApi';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';

export default function Wellness() {
  const { settings, loading: siteLoading } = useSite();
  const treatments = useApi(siteApi.treatments, []);
  usePageMotion(!treatments.loading && !siteLoading);

  return (
    <>
      <PageHero image="/assets/img/spa-ritual.jpg" alt="Candles and spa oils" width="800" height="546"
        kicker="Wellness" title="Kai Wellness Spa"
        lede="A refined space to slow down, restore and leave the pace of the city behind." />

      <section className="section feature" aria-labelledby="spa-title">
        <div className="wrap split">
          <div className="feature__media feature__media--parallax" data-clip="">
            <img src="/assets/img/spa.jpg" alt="Spa treatment" width="800" height="546" loading="lazy" data-parallax="" />
          </div>
          <div className="stack" data-reveal="">
            <p className="kicker">The Spa</p>
            <h2 id="spa-title">Restore, rebalance, renew.</h2>
            <p>Kai Wellness Spa offers tailored therapies, soothing massages and restorative rituals, delivered by experienced therapists.</p>
            <p>Guests leave refreshed, balanced and renewed — whether after a long flight or a full day of meetings.</p>
            <Link className="btn" to="/wellness#book-spa">Book a Treatment</Link>
          </div>
        </div>
      </section>

      <section className="section bg-alt" aria-labelledby="treatments-title">
        <div className="wrap">
          <div className="section-head">
            <div className="stack stack--tight">
              <p className="kicker">Treatments</p>
              <h2 id="treatments-title">Our therapies</h2>
            </div>
          </div>
          <StateMessage loading={treatments.loading} error={treatments.error} onRetry={treatments.reload}
            empty={treatments.data && !treatments.data.length ? 'Our therapy menu is being updated. Please contact the spa.' : null} />
          {treatments.data && treatments.data.length > 0 && (
            <CardGrid cards={treatments.data} render={(t) => (
              <p className="card__meta">{[t.duration_label, t.price_label].filter(Boolean).join(' · ')}</p>
            )} />
          )}
        </div>
      </section>

      <DetailsStrip className="section on-brand" label="Spa details" items={settings.spa_details} />

      <section className="section" id="book-spa" aria-labelledby="book-spa-title">
        <div className="wrap split split--top">
          <div className="stack" data-reveal="">
            <p className="kicker">Appointments</p>
            <h2 id="book-spa-title">Book a treatment</h2>
            <p className="intro__body">Choose a therapy and a time. Our spa team will confirm your appointment.</p>
          </div>
          <SpaAppointmentForm key={treatments.data ? 'ready' : 'loading'} treatments={treatments.data} />
        </div>
      </section>
    </>
  );
}

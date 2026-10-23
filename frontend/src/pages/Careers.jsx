import { Link } from 'react-router-dom';
import { ApplicationForm } from '../components/forms/SiteForms';
import { CardGrid, PageHero, StateMessage } from '../components/Sections';
import { useSite } from '../context/SiteContext';
import { useApi } from '../hooks/useApi';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';

export default function Careers() {
  const { settings, loading: siteLoading } = useSite();
  const teams = useApi(() => siteApi.cards('career_teams'), []);
  const openings = useApi(siteApi.openings, []);
  usePageMotion(!teams.loading && !openings.loading && !siteLoading);

  return (
    <>
      {/* Swap for a team photo when available (e.g. /assets/img/careers.jpg). */}
      <PageHero image="/assets/img/hero-city.jpg" alt="City skyline at dusk" width="1920" height="1280"
        kicker="Careers" title="Build your career in hospitality" lede="Join the team behind The Tycoons Hotel, Bengaluru." />

      <section className="section intro">
        <div className="wrap split">
          <h2 data-reveal="">Hospitality, done with care.</h2>
          <p className="intro__body" data-reveal="">We look for people who take pride in the details — a warm welcome, a well-kept room, a memorable meal. Whether you are starting out or bringing years of experience, we would like to hear from you.</p>
        </div>
      </section>

      <section className="section bg-alt" aria-labelledby="teams-title">
        <div className="wrap">
          <div className="section-head">
            <div className="stack stack--tight">
              <p className="kicker">Where you could work</p>
              <h2 id="teams-title">Our teams</h2>
            </div>
          </div>
          <StateMessage loading={teams.loading} error={teams.error} onRetry={teams.reload} />
          {teams.data && <CardGrid cards={teams.data} />}
        </div>
      </section>

      <section className="section" aria-labelledby="roles-title">
        <div className="wrap">
          <div className="section-head">
            <div className="stack stack--tight">
              <p className="kicker">Open positions</p>
              <h2 id="roles-title">Current openings</h2>
            </div>
          </div>
          <StateMessage loading={openings.loading} error={openings.error} onRetry={openings.reload} />
          {openings.data && (
            <ul className="roles" data-reveal-children="">
              {openings.data.length === 0 && <li className="roles__empty">There are no open positions right now.</li>}
              {openings.data.map((o) => (
                <li key={o.id}>
                  <div><h3>{o.title}</h3><p>{o.department} · {o.employment_type}</p></div>
                  <Link className="link" to="/careers#apply" state={{ position: o.title, openingId: o.id }}>Apply</Link>
                </li>
              ))}
            </ul>
          )}
          <p className="roles__note" data-reveal="">Don’t see the right role? Send us your CV and tell us where you would like to work.</p>
        </div>
      </section>

      <section className="section bg-alt" id="apply" aria-labelledby="apply-title">
        <div className="wrap split split--top">
          <div className="stack" data-reveal="">
            <p className="kicker">Apply</p>
            <h2 id="apply-title">Send your application</h2>
            <p className="intro__body">Share a few details and our team will be in touch.</p>
            <dl className="contact-list">
              <div><dt>Careers</dt><dd>{settings.careers_email_display}</dd></div>
            </dl>
          </div>
          <ApplicationForm />
        </div>
      </section>
    </>
  );
}

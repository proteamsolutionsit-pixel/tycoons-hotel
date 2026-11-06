import { Link } from 'react-router-dom';
import BookingBar from '../components/BookingBar';
import { DetailsStrip, PageHero, StateMessage } from '../components/Sections';
import { useSite } from '../context/SiteContext';
import { useApi } from '../hooks/useApi';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';
import { rupees, tariffLine } from '../utils/format';

export default function Rooms() {
  const { settings, loading: siteLoading } = useSite();
  const rooms = useApi(siteApi.rooms, []);
  usePageMotion(!rooms.loading && !siteLoading);

  return (
    <>
      <PageHero booking image="/assets/img/gal-suite.jpg" alt="Suite living area" width="900" height="600"
        kicker="Accommodations" title="Rooms & Suites" lede="Rooms and suites, designed for rest between busy days." />
      <BookingBar className="booking booking--page" />

      <section className="section intro">
        <div className="wrap split">
          <h2 data-reveal="">Quiet luxury, whether you stay a night or a week.</h2>
          <p className="intro__body" data-reveal="">Refined interiors, plush bedding, premium amenities and thoughtful service. Every room is set up for work and rest alike — with the privacy and calm a business trip deserves.</p>
        </div>
      </section>

      {!rooms.data && (
        <section className="section bg-alt"><div className="wrap">
          <StateMessage loading={rooms.loading} error={rooms.error} onRetry={rooms.reload}>Loading rooms…</StateMessage>
        </div></section>
      )}
      {rooms.data?.map((r, i) => (
        <section key={r.slug} aria-labelledby={`room-${r.slug}`}
          className={'section feature feature--bleed room-row' + (i % 2 ? ' feature--rev' : ' bg-alt')}>
          <div className="wrap split">
            <div className="feature__media feature__media--parallax" data-clip="">
              <img src={r.image_url} alt={r.image_alt || r.name} loading="lazy" data-parallax="" />
            </div>
            <div className="stack" data-reveal="">
              <h2 id={`room-${r.slug}`}>{r.name}</h2>
              <p>{r.description}</p>
              <ul className="facts">
                <li>{r.size_label}</li>
                <li>{r.bed_label}</li>
                <li>{r.view_label}</li>
                <li>{r.occupancy_label}</li>
              </ul>
              <div className="price-row">
                <Link className="btn" to={`/rooms?room=${encodeURIComponent(r.slug)}#book`}>Check Availability</Link>
                {(r.single_rate_paise != null || r.inclusions) && (
                  <span className="price-row__rate">
                    {[r.single_rate_paise != null ? `${tariffLine(r.base_rate_paise, r.single_rate_paise, '')} per night`
                      : `${rupees(r.base_rate_paise)} per night`, r.inclusions].filter(Boolean).join(' · ')}
                  </span>
                )}
              </div>
            </div>
          </div>
        </section>
      ))}

      <DetailsStrip label="Stay details" items={settings.stay_details} />
    </>
  );
}

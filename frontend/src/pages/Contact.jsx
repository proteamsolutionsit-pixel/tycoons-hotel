import { ContactForm } from '../components/forms/SiteForms';
import { PageHero } from '../components/Sections';
import { useContact, useSite } from '../context/SiteContext';
import { usePageMotion } from '../motion/usePageMotion';
import { isFilled } from '../utils/format';

const MAP_EMBED = /^https:\/\/(www\.)?google\.[a-z.]+\/maps\/embed\?/;

export default function Contact() {
  const { settings, loading } = useSite();
  const c = useContact();
  usePageMotion(!loading);
  const mapUrl = MAP_EMBED.test(settings.map_embed_url || '') ? settings.map_embed_url : null;
  const gettingHere = (settings.getting_here || []).filter((g) => isFilled(g.value));

  return (
    <>
      <PageHero image="/assets/img/hero-city.jpg" alt="City skyline at dusk" width="1920" height="1280"
        kicker="Contact" title="We would love to host you" lede="Reservations, dining or spa — our team is here to help." />

      <section className="section" aria-labelledby="touch-title">
        <div className="wrap split split--top">
          <div className="stack" data-reveal="">
            <p className="kicker">Get in touch</p>
            <h2 id="touch-title">The Tycoons Hotel</h2>
            <dl className="contact-list">
              {(c.street || c.city || c.regionPin) && (
                <div><dt>Address</dt><dd>{c.street}{c.street && <br />}{c.city}{c.city && c.regionPin ? ', ' : ''}{c.regionPin}</dd></div>
              )}
              {(c.phone || c.email) && <div><dt>Reservations</dt><dd>{[c.phone, c.email].filter(Boolean).join(' · ')}</dd></div>}
              {c.landlines.map((l, i) => (
                <div key={i}><dt>{l.label || 'Landline'}</dt><dd>{l.tel ? <a className="u-draw" href={l.tel}>{l.number}</a> : l.number}</dd></div>
              ))}
              {/* Shown only once the hotel has filled them in (placeholders are hidden) */}
              {isFilled(settings.dining_phone_display) && <div><dt>Fishy Tales</dt><dd>{settings.dining_phone_display}</dd></div>}
              {isFilled(settings.spa_phone_display) && <div><dt>Kai Wellness Spa</dt><dd>{settings.spa_phone_display}</dd></div>}
            </dl>
          </div>
          <ContactForm />
        </div>
      </section>

      <section className="section bg-alt" aria-labelledby="here-title">
        <div className="wrap split">
          {mapUrl ? (
            <div className="map-embed" data-reveal="">
              <iframe src={mapUrl} title="Map showing The Tycoons Hotel" loading="lazy" referrerPolicy="no-referrer-when-downgrade" allowFullScreen />
            </div>
          ) : (
            <div className="map-slot" data-reveal="">Map — embed Google Maps for [street address]</div>
          )}
          <div className="stack" data-reveal="">
            <p className="kicker">Getting here</p>
            <h2 id="here-title">In the heart of Bengaluru</h2>
            {gettingHere.length > 0 && (
              <dl className="contact-list">
                {gettingHere.map((g, i) => <div key={i}><dt>{g.label}</dt><dd>{g.value}</dd></div>)}
              </dl>
            )}
          </div>
        </div>
      </section>
    </>
  );
}

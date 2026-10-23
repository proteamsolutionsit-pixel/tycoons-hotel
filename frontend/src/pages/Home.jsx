import { Link } from 'react-router-dom';
import BookingBar from '../components/BookingBar';
import { NewsletterForm } from '../components/forms/SiteForms';
import HeroSlideshow from '../components/home/HeroSlideshow';
import Marquee from '../components/home/Marquee';
import RoomsCarousel from '../components/home/RoomsCarousel';
import { GalleryButton } from '../components/Lightbox';
import { StateMessage } from '../components/Sections';
import { ScrubWords, SplitText } from '../components/SplitText';
import { useSite } from '../context/SiteContext';
import { useApi } from '../hooks/useApi';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';

export default function Home() {
  const { settings, loading: siteLoading } = useSite();
  const rooms = useApi(siteApi.rooms, []);
  const gallery = useApi(() => siteApi.gallery({ home: true }), []);
  usePageMotion(!rooms.loading && !gallery.loading && !siteLoading);
  const galleryItems = (gallery.data?.items || []).map((g) => ({ src: g.image_url, alt: g.alt }));

  return (
    <>
      <HeroSlideshow />
      <BookingBar />

      {/* Vision */}
      <section className="section vision" id="vision">
        <div className="wrap split">
          <div className="stack" data-reveal-children="">
            <p className="kicker">Our Vision</p>
            <SplitText as="h2" text="A sanctuary where business, comfort and wellbeing meet." />
          </div>
          <div className="stack vision__body">
            <ScrubWords text="The Tycoons Hotel pairs elegant stays and personalised hospitality with exceptional dining and restorative wellness. Every detail — from a warm welcome to a peaceful night's rest — is designed for guests travelling to work, to celebrate, or simply to recharge." />
            <p className="vision__coda" data-reveal="">Here, luxury is never loud. It is felt in the details.</p>
          </div>
        </div>
      </section>

      <Marquee items={settings.amenities || []} />

      {rooms.data ? <RoomsCarousel rooms={rooms.data} /> : (
        <section className="section bg-alt rooms" id="stay" aria-labelledby="rooms-title">
          <div className="wrap">
            <h2 id="rooms-title">Rooms &amp; Suites</h2>
            <StateMessage loading={rooms.loading} error={rooms.error} onRetry={rooms.reload} />
          </div>
        </section>
      )}

      {/* Meetings / lounge */}
      <section className="section feature" id="meetings" aria-labelledby="meetings-title">
        <div className="wrap split">
          <div className="feature__media feature__media--parallax" data-clip="">
            <img src="/assets/img/lounge.jpg" alt="Business lounge" width="1200" height="800" loading="lazy" data-parallax="" />
          </div>
          <div className="stack" data-reveal-children="">
            <p className="kicker">Business Lounge</p>
            <SplitText as="h2" id="meetings-title" text="Built for the way you work." />
            <p>A business lounge and dependable connectivity, with a team that handles every detail of your stay.</p>
            <ul className="facts">
              {(settings.lounge_facts || []).map((t, i) => <li key={i}>{t}</li>)}
            </ul>
            <Link className="btn" to="/meetings">Explore the Lounge</Link>
          </div>
        </div>
      </section>

      {/* Dining */}
      <section className="section feature feature--rev feature--bleed on-brand" id="dining" aria-labelledby="dining-title">
        <div className="wrap split">
          <div className="feature__media feature__media--parallax" data-clip="">
            <img src="/assets/img/dining-dish.jpg" alt="Fishy Tales seafood dish" width="1200" height="800" loading="lazy" data-parallax="" />
          </div>
          <div className="stack" data-reveal-children="">
            <p className="kicker">Signature Dining</p>
            <SplitText as="h2" id="dining-title" text="Fishy Tales" />
            <p className="subtitle">Coastal restaurant</p>
            <p>The freshest catch meets bold coastal flavour. From expertly prepared classics to contemporary seafood creations — for intimate dinners, family gatherings and client evenings.</p>
            <div className="actions">
              <Link className="btn btn--gold" to="/dining#reserve">Reserve a Table</Link>
              <Link className="btn btn--ghost" to="/dining">View Menu</Link>
            </div>
          </div>
        </div>
      </section>

      {/* Wellness */}
      <section className="section feature feature--bleed bg-alt" id="wellness" aria-labelledby="wellness-title">
        <div className="wrap split">
          <div className="feature__media feature__media--parallax" data-clip="">
            <img src="/assets/img/spa.jpg" alt="Kai Wellness Spa treatment" width="800" height="546" loading="lazy" data-parallax="" />
          </div>
          <div className="stack" data-reveal-children="">
            <p className="kicker">Wellness</p>
            <SplitText as="h2" id="wellness-title" text="Kai Wellness Spa" />
            <p className="subtitle">Restore, rebalance, renew</p>
            <p>Tailored therapies, soothing massages and restorative rituals by experienced therapists — an unhurried escape from the pace of the city.</p>
            <Link className="btn" to="/wellness">Book a Treatment</Link>
          </div>
        </div>
      </section>

      {/* Gallery */}
      <section className="section gallery" id="gallery" aria-labelledby="gallery-title">
        <div className="wrap">
          <div className="section-head">
            <SplitText as="h2" id="gallery-title" text="A glimpse of the Tycoons experience" />
            <Link className="link" to="/gallery" data-reveal="">Full gallery</Link>
          </div>
          <StateMessage loading={gallery.loading} error={gallery.error} onRetry={gallery.reload} />
          {gallery.data && (
            <ul className="gallery__grid" data-stagger="">
              {gallery.data.items.map((g, i) => (
                <li key={g.id}><GalleryButton image={g} list={galleryItems} index={i} /></li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {/* Newsletter */}
      <section className="section bg-alt newsletter" aria-labelledby="newsletter-title">
        <div className="wrap split">
          <div className="stack stack--tight" data-reveal-children="">
            <SplitText as="h2" id="newsletter-title" text="Be the first to hear from the Tycoons." />
            <p>Offers, dining evenings and wellness rituals — occasionally, never noisily.</p>
          </div>
          <NewsletterForm />
        </div>
      </section>
    </>
  );
}

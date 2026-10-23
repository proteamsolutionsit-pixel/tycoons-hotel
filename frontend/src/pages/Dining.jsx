import { Link } from 'react-router-dom';
import { ReserveTableForm } from '../components/forms/SiteForms';
import { CardGrid, DetailsStrip, PageHero, StateMessage } from '../components/Sections';
import { useSite } from '../context/SiteContext';
import { useApi } from '../hooks/useApi';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';

export default function Dining() {
  const { settings, loading: siteLoading } = useSite();
  const cards = useApi(() => siteApi.cards('dining_menu'), []);
  usePageMotion(!cards.loading && !siteLoading);
  const menuPdf = settings.dining_menu_pdf_url;

  return (
    <>
      <PageHero image="/assets/img/dining-dish.jpg" alt="Seafood dish at Fishy Tales" width="1200" height="800"
        kicker="Signature Dining" title="Fishy Tales"
        lede="Our coastal restaurant, where the freshest catch meets bold flavour and refined dining." />

      <section className="section feature feature--rev" aria-labelledby="restaurant-title">
        <div className="wrap split">
          <div className="feature__media feature__media--parallax" data-clip="">
            <img src="/assets/img/gal-restaurant.jpg" alt="Restaurant table setting" width="800" height="522" loading="lazy" data-parallax="" />
          </div>
          <div className="stack" data-reveal="">
            <p className="kicker">The Restaurant</p>
            <h2 id="restaurant-title">Coastal flavour, refined.</h2>
            <p>From expertly prepared coastal classics to contemporary seafood creations, every dish at Fishy Tales celebrates the richness of the sea.</p>
            <p>Set in an elegant, inviting room — for intimate dinners, family gatherings, client evenings and special occasions.</p>
            <Link className="btn" to="/dining#reserve">Reserve a Table</Link>
          </div>
        </div>
      </section>

      <section className="section bg-alt" aria-labelledby="menu-title">
        <div className="wrap">
          <div className="section-head">
            <div className="stack stack--tight">
              <p className="kicker">On the menu</p>
              <h2 id="menu-title">Three ways to dine</h2>
            </div>
            {menuPdf
              ? <a className="link" href={menuPdf} target="_blank" rel="noopener noreferrer">Download menu</a>
              : <Link className="link" to="/dining#reserve">Download menu [PDF]</Link>}
          </div>
          <StateMessage loading={cards.loading} error={cards.error} onRetry={cards.reload} />
          {cards.data && <CardGrid cards={cards.data} />}
        </div>
      </section>

      <DetailsStrip className="section on-brand" label="Restaurant details" items={settings.dining_details} />

      <section className="section" id="reserve" aria-labelledby="reserve-title">
        <div className="wrap split split--top">
          <div className="stack" data-reveal="">
            <p className="kicker">Reservations</p>
            <h2 id="reserve-title">Reserve a table</h2>
            <p className="intro__body">Tell us when you would like to join us. Our team will confirm your table by phone or email.</p>
          </div>
          <ReserveTableForm />
        </div>
      </section>
    </>
  );
}

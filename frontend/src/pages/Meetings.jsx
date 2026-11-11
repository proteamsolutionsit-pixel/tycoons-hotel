import { BusinessEnquiryForm } from '../components/forms/SiteForms';
import { CardGrid, PageHero, StateMessage } from '../components/Sections';
import { useSite } from '../context/SiteContext';
import { useApi } from '../hooks/useApi';
import { usePageMotion } from '../motion/usePageMotion';
import { siteApi } from '../services/api';

export default function Meetings() {
  const { settings, loading: siteLoading } = useSite();
  const cards = useApi(() => siteApi.cards('lounge_spaces'), []);
  usePageMotion(!cards.loading && !siteLoading);

  return (
    <>
      <PageHero image="/assets/img/lounge.jpg" alt="Business lounge" width="1200" height="800"
        kicker="Business Lounge" title="Built for the way you work"
        lede="A business lounge and a team that takes care of every detail." />

      <section className="section feature" aria-labelledby="work-title">
        <div className="wrap split">
          <div className="feature__media feature__media--parallax" data-clip="">
            <img src="/assets/img/lobby-lounge.jpg" alt="Hotel lounge" width="600" height="417" loading="lazy" data-parallax="" />
          </div>
          <div className="stack" data-reveal="">
            <p className="kicker">For business travellers</p>
            <h2 id="work-title">Work well. Rest well.</h2>
            <p>The Tycoons Hotel is designed around the rhythm of a business trip — focused days, easy evenings and a quiet night's rest.</p>
            {settings.lounge_work_note && <p>{settings.lounge_work_note}</p>}
          </div>
        </div>
      </section>

      <section className="section bg-alt" aria-labelledby="spaces-title">
        <div className="wrap">
          <div className="section-head">
            <div className="stack stack--tight">
              <p className="kicker">Spaces</p>
              <h2 id="spaces-title">Work, meet, host</h2>
            </div>
          </div>
          <StateMessage loading={cards.loading} error={cards.error} onRetry={cards.reload} />
          {cards.data && <CardGrid cards={cards.data} two />}
        </div>
      </section>

      <section className="section" id="proposal" aria-labelledby="proposal-title">
        <div className="wrap split split--top">
          <div className="stack" data-reveal="">
            <p className="kicker">Business enquiries</p>
            <h2 id="proposal-title">Plan your business stay</h2>
            <p className="intro__body">Share a few details and our team will get back to you.</p>
          </div>
          <BusinessEnquiryForm />
        </div>
      </section>
    </>
  );
}

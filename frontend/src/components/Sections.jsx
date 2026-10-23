/* Building blocks shared by the inner pages. Markup and classes are the
   original's; content comes from props / the API. */
import { SplitText } from './SplitText';

export function PageHero({ image, alt, width, height, kicker, title, lede, booking = false }) {
  return (
    <section className={'page-hero' + (booking ? ' page-hero--booking' : '')} aria-labelledby="page-title">
      <figure className="page-hero__media">
        <img src={image} alt={alt} width={width} height={height} fetchpriority="high" />
      </figure>
      <div className="page-hero__content">
        <p className="kicker" data-hero-fade="">{kicker}</p>
        <SplitText as="h1" id="page-title" mode="lines" text={title} />
        <p className="page-hero__lede" data-hero-fade="">{lede}</p>
      </div>
    </section>
  );
}

export function DetailsStrip({ items, label, className = 'section bg-alt' }) {
  return (
    <section className={className} aria-label={label}>
      <div className="wrap">
        <ul className="details" data-stagger="">
          {(items || []).map((d, i) => (
            <li key={i}><span className="details__label">{d.label}</span><span className="details__value">{d.value}</span></li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function StateMessage({ loading, error, empty, onRetry, children }) {
  if (loading) return <p className="state-msg" role="status">{children || 'Loading…'}</p>;
  if (error) {
    return (
      <p className="state-msg state-msg--error" role="alert">
        {error.message || 'This section could not be loaded.'}
        {onRetry && <button type="button" className="link" onClick={onRetry} style={{ background: 'none', border: 0 }}>Try again</button>}
      </p>
    );
  }
  if (empty) return <p className="state-msg">{empty}</p>;
  return null;
}

/** A grid of content cards (dining menu, lounge spaces, career teams, spa therapies). */
export function CardGrid({ cards, two = false, render }) {
  return (
    <ul className={'cards' + (two ? ' cards--two' : '')} data-stagger="">
      {cards.map((c) => (
        <li className="card" key={c.id}>
          <span className="card__media zoom"><img src={c.image_url} alt={c.image_alt} loading="lazy" /></span>
          <div className="card__body">
            <h3>{c.title ?? c.name}</h3>
            <p>{c.body ?? c.description}</p>
            {render ? render(c) : c.meta ? <p className="card__meta">{c.meta}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

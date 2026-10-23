import { useCallback, useEffect, useRef, useState } from 'react';

/** Load data on mount (and when deps change). Returns {data, error, loading, reload}. */
export function useApi(fetcher, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const seq = useRef(0);

  const load = useCallback(() => {
    const id = ++seq.current;
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.resolve()
      .then(fetcher)
      .then((data) => { if (id === seq.current) setState({ data, error: null, loading: false }); })
      .catch((error) => { if (id === seq.current) setState({ data: null, error, loading: false }); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
    return () => { seq.current += 1; };
  }, [load]);

  return { ...state, reload: load };
}

export function useDocumentTitle(title) {
  useEffect(() => {
    if (title) document.title = title;
  }, [title]);
}

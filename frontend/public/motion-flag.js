/* Motion flag, set before paint (as in the original design). Kept as a
   blocking external script so the Content-Security-Policy needs no
   'unsafe-inline' for scripts. */
if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) document.documentElement.classList.add('motion');

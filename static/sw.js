/* Service worker: l'app si apre anche senza rete.

   La casa puo' restare senza connessione, e l'app deve almeno aprirsi: la
   pagina, il foglio di stile e il codice stanno in una copia locale. Non e' un
   "funziona tutto offline": i dati (dispensa, piano, notizie) vivono sul
   server, e senza rete quelli non ci sono — e' il server a saperlo dire. Qui si
   salva **la scocca**, che e' quello che rende l'app un'app e non una pagina
   bianca di errore.

   La strategia dipende da cosa si chiede:
   - le pagine: prima la rete, cosi' un aggiornamento arriva subito; se la rete
     manca, la copia salvata.
   - i file statici: prima la copia, perche' hanno gia' la versione
     nell'indirizzo (`?v=...`) e quindi non possono essere vecchi.
   - le API: mai la copia. Un dato vecchio mostrato come fresco e' peggio di un
     dato mancante: la dispensa di ieri non e' la dispensa di oggi. */

const CACHE = 'maggiordomo-scocca-v1';

// La scocca minima. `app.js` e `style.css` senza versione: la richiesta vera
// porta `?v=...`, e la ricerca in cache ignora la parte dopo `?` (vedi sotto).
const SCOCCA = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json',
  '/static/icons/icona.svg',
  '/static/icons/icona-180.png',
  '/static/icons/icona-512.png',
];

self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((cache) =>
      // `addAll` fallisce tutto se un file manca: con `allSettled` si salva
      // quello che c'e', e un'icona assente non impedisce l'installazione
      Promise.allSettled(SCOCCA.map((url) => cache.add(url)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((chiavi) => Promise.all(
        chiavi.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// La chiave della cache senza `?v=...`: cosi' la copia salvata all'installazione
// (senza versione) risponde anche alla richiesta versionata della pagina.
function chiave(request) {
  const url = new URL(request.url);
  url.search = '';
  return url.toString();
}

self.addEventListener('fetch', (evento) => {
  const richiesta = evento.request;
  const url = new URL(richiesta.url);
  if (richiesta.method !== 'GET' || url.origin !== self.location.origin) return;

  // le API non si salvano: un dato vecchio non deve sembrare fresco
  if (url.pathname.startsWith('/api/')) return;

  if (richiesta.mode === 'navigate') {
    evento.respondWith(
      fetch(richiesta)
        .then((risposta) => {
          const copia = risposta.clone();
          caches.open(CACHE).then((cache) => cache.put('/', copia));
          return risposta;
        })
        .catch(() => caches.match('/'))
    );
    return;
  }

  evento.respondWith(
    caches.match(chiave(richiesta)).then((salvata) => {
      if (salvata) return salvata;
      return fetch(richiesta).then((risposta) => {
        if (risposta.ok && url.pathname.startsWith('/static/')) {
          const copia = risposta.clone();
          caches.open(CACHE).then((cache) => cache.put(chiave(richiesta), copia));
        }
        return risposta;
      });
    })
  );
});

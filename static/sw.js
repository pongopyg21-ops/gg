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
   - i file statici: **anche qui prima la rete**, con la copia salvata solo come
     ripiego. Non "prima la copia": `chiave()` ignora `?v=...`, quindi la copia
     salvata all'installazione non ha versione e risponderebbe a qualunque
     richiesta — anche a una versione nuova. Il risultato era che `app.js`
     restava quello di quando l'app era stata installata, mentre `index.html`
     (prima la rete) si aggiornava: la pagina nuova chiedeva funzioni che il
     codice vecchio non aveva, e la sezione restava invisibile. Il `?v=...` c'e'
     apposta, per distinguere le versioni: va usato mentre c'e' rete.
   - le API: mai la copia. Un dato vecchio mostrato come fresco e' peggio di un
     dato mancante: la dispensa di ieri non e' la dispensa di oggi. */

const CACHE = 'maggiordomo-scocca-v10';

// La scocca minima. `app.js` e `style.css` senza versione: la richiesta vera
// porta `?v=...`, e la ricerca in cache ignora la parte dopo `?` (vedi sotto).
const SCOCCA = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/snake.js',
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
// (senza versione) risponde anche alla richiesta versionata quando la rete manca.
function chiave(request) {
  const url = new URL(request.url);
  url.search = '';
  return url.toString();
}

// I file statici si chiedono prima alla rete, **anche se c'e' una copia**: le
// versioni nuove devono poter arrivare. La copia resta solo per quando la rete
// manca. Salvare solo le risposte `ok` evita di conservare un errore.
function serveStatico(richiesta) {
  return fetch(richiesta)
    .then((risposta) => {
      if (risposta.ok) {
        const copia = risposta.clone();
        caches.open(CACHE).then((cache) => cache.put(chiave(richiesta), copia));
      }
      return risposta;
    })
    .catch(() => caches.match(chiave(richiesta)));
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

  // i file statici si chiedono prima alla rete: e' cosi' che una versione nuova
  // di `app.js` arriva a chi ha gia' l'app installata (vedi `serveStatico`)
  evento.respondWith(serveStatico(richiesta));
});

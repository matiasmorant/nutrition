const CACHE_NAME = 'optimal-nutrition-v4';
const DATA_CACHE_NAME = 'optimal-nutrition-data-v2';

// Core app files that must be cached
const CORE_ASSETS = [
  './',
  './index.html',
  './dataService.js',
  './manifest.json',
  './icon-192.png',
  './icon-512.png'
];

// External CDN dependencies
const CDN_ASSETS = [
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/tabulator-tables@5.6.1/dist/css/tabulator_modern.min.css',
  'https://unpkg.com/papaparse@latest/papaparse.min.js',
  'https://unpkg.com/tabulator-tables@5.6.1/dist/js/tabulator.min.js',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap',
  'https://cdn.jsdelivr.net/npm/alpinejs@3.13.10/dist/cdn.min.js',
  'https://cdn.jsdelivr.net/npm/ml-matrix/matrix.umd.min.js',
  'https://www.lactame.com/lib/ml/6.0.0/ml.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/mathjs/12.3.0/math.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/chart.js',
  'https://cdn.jsdelivr.net/npm/idb@8/build/umd.js'
];

// Data files
const DATA_ASSETS = [
  './foodnutrient.csv',
  './nutrientTree.txt',
  './nutrientinfo.md',
  './diets.json'
];

// Install event - cache all resources
self.addEventListener('install', event => {
  console.log('[ServiceWorker] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[ServiceWorker] Caching core assets');
      return cache.addAll(CORE_ASSETS.map(url => new Request(url, { mode: 'no-cors' })))
        .catch(err => {
          console.warn('[ServiceWorker] Failed to cache some core assets:', err);
          return Promise.resolve();
        });
    }).then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[ServiceWorker] Activating...');
  const cacheWhitelist = [CACHE_NAME, DATA_CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (!cacheWhitelist.includes(cacheName)) {
            console.log('[ServiceWorker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Pre-cache CDN and Data assets in background
      caches.open(CACHE_NAME).then(cache => {
        CDN_ASSETS.forEach(url => {
          fetch(url, { mode: 'cors' }).then(res => res.ok && cache.put(url, res)).catch(() => {});
        });
      });
      caches.open(DATA_CACHE_NAME).then(cache => {
        DATA_ASSETS.forEach(url => {
          fetch(url).then(res => res.ok && cache.put(url, res)).catch(() => {});
        });
      });
      return self.clients.claim();
    })
  );
});

// Fetch event - Stale-While-Revalidate
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') return;

  // Determine which cache to use
  const isDataAsset = DATA_ASSETS.some(asset => url.pathname.includes(asset.replace('./', '')));
  const cacheToUse = isDataAsset ? DATA_CACHE_NAME : CACHE_NAME;

  event.respondWith(
    caches.open(cacheToUse).then(cache => {
      return cache.match(event.request).then(cachedResponse => {
        const fetchPromise = fetch(event.request).then(networkResponse => {
          // If network request is successful, update the cache
          if (networkResponse && networkResponse.status === 200) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        }).catch(err => {
          // Fallback for HTML navigation if network fails and no cache
          if (event.request.headers.get('accept').includes('text/html')) {
            return caches.match('./index.html');
          }
          throw err;
        });

        // Return cached response immediately if it exists, otherwise wait for network
        return cachedResponse || fetchPromise;
      });
    })
  );
});
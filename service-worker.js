const CACHE_NAME = 'optimal-nutrition-v5';
const DATA_CACHE_NAME = 'optimal-nutrition-data-v2';

const CORE_ASSETS = [
  './',
  './index.html',
  './dataService.js',
  './manifest.json',
  './icon-192.png',
  './icon-512.png'
];

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

const DATA_ASSETS = [
  './foodnutrient.csv',
  './nutrientTree.txt',
  './nutrientinfo.md',
  './diets.json'
];

// Install event
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // ONLY cache local core assets here
      console.log('[SW] Pre-caching local core assets');
      return cache.addAll(CORE_ASSETS); 
    }).then(() => self.skipWaiting())
  );
});

// Activate event
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME, DATA_CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (!cacheWhitelist.includes(cacheName)) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  if (event.request.method !== 'GET') return;

  // 1. Cache-First Strategy for CDN Assets (Prevents network request entirely)
  const isCDNAsset = CDN_ASSETS.some(asset => event.request.url.includes(asset));
  
  if (isCDNAsset) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        return cachedResponse || fetch(event.request).then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // 2. Stale-While-Revalidate Strategy for Data and Core Assets
  const isDataAsset = DATA_ASSETS.some(asset => url.pathname.includes(asset.replace('./', '')));
  const targetCache = isDataAsset ? DATA_CACHE_NAME : CACHE_NAME;

  event.respondWith(
    caches.open(targetCache).then(cache => {
      return cache.match(event.request).then(cachedResponse => {
        const fetchPromise = fetch(event.request).then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        }).catch(err => {
          console.warn('[SW] Network fetch failed, using cache only:', err);
        });

        return cachedResponse || fetchPromise;
      });
    })
  );
});
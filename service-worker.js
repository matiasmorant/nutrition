const CACHE_NAME = 'optimal-nutrition-v2';
const DATA_CACHE_NAME = 'optimal-nutrition-data-v1';

// Core app files that must be cached
const CORE_ASSETS = [
  '/',
  '/index.html',
  '/dataService.js',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png'
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
  'https://cdnjs.cloudflare.com/ajax/libs/mathjs/12.3.0/math.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/chart.js',
  'https://cdn.jsdelivr.net/npm/idb@8/build/umd.js'
];

// Data files (optional - app may work without these if user has added their own data)
const DATA_ASSETS = [
  '/foodnutrient.csv',
  '/nutrientTree.txt',
  '/nutrientinfo.md',
  '/diets.json'
];

// Install event - cache all resources
self.addEventListener('install', event => {
  console.log('[ServiceWorker] Installing...');
  
  event.waitUntil(
    Promise.all([
      // Cache core assets (must succeed)
      caches.open(CACHE_NAME).then(cache => {
        console.log('[ServiceWorker] Caching core assets');
        return cache.addAll(CORE_ASSETS);
      }),
      
      // Cache CDN assets (must succeed for offline)
      caches.open(CACHE_NAME).then(cache => {
        console.log('[ServiceWorker] Caching CDN assets');
        return cache.addAll(CDN_ASSETS);
      }),
      
      // Cache data assets (optional - don't fail if missing)
      caches.open(DATA_CACHE_NAME).then(cache => {
        console.log('[ServiceWorker] Caching data assets');
        return Promise.allSettled(
          DATA_ASSETS.map(url => 
            cache.add(url).catch(err => {
              console.warn(`[ServiceWorker] Failed to cache ${url}:`, err);
            })
          )
        );
      })
    ]).then(() => {
      console.log('[ServiceWorker] Installation complete');
      // Force the waiting service worker to become the active service worker
      return self.skipWaiting();
    })
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
      console.log('[ServiceWorker] Activation complete');
      // Take control of all pages immediately
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Handle data files with network-first strategy (fresher data when online)
  if (DATA_ASSETS.some(asset => url.pathname.endsWith(asset))) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // If fetch succeeds, update cache and return response
          const responseClone = response.clone();
          caches.open(DATA_CACHE_NAME).then(cache => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // If fetch fails (offline), return cached version
          return caches.match(event.request);
        })
    );
    return;
  }
  
  // Handle all other requests with cache-first strategy
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      if (cachedResponse) {
        // Return cached version immediately
        return cachedResponse;
      }
      
      // Not in cache, fetch from network
      return fetch(event.request).then(response => {
        // Don't cache non-successful responses or non-GET requests
        if (!response || response.status !== 200 || event.request.method !== 'GET') {
          return response;
        }
        
        // Cache the fetched response for future use
        const responseClone = response.clone();
        const cacheName = CDN_ASSETS.some(asset => event.request.url.includes(asset)) 
          ? CACHE_NAME 
          : DATA_CACHE_NAME;
          
        caches.open(cacheName).then(cache => {
          cache.put(event.request, responseClone);
        });
        
        return response;
      }).catch(error => {
        console.error('[ServiceWorker] Fetch failed:', error);
        // Could return a custom offline page here
        throw error;
      });
    })
  );
});
const CACHE_NAME = 'optimal-nutrition-v3';
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

// External CDN dependencies - use cache-first approach
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
    // Cache core assets first (most important)
    caches.open(CACHE_NAME).then(cache => {
      console.log('[ServiceWorker] Caching core assets');
      return cache.addAll(CORE_ASSETS.map(url => new Request(url, { mode: 'no-cors' })))
        .catch(err => {
          console.warn('[ServiceWorker] Failed to cache some core assets:', err);
          // Continue even if some assets fail
          return Promise.resolve();
        });
    }).then(() => {
      console.log('[ServiceWorker] Core assets cached');
      
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
      
      // Pre-cache CDN assets in background
      self.caches.open(CACHE_NAME).then(cache => {
        CDN_ASSETS.forEach(url => {
          fetch(url, { mode: 'cors' })
            .then(response => {
              if (response.ok) {
                return cache.put(url, response);
              }
            })
            .catch(err => {
              console.warn(`[ServiceWorker] Failed to cache CDN asset ${url}:`, err);
            });
        });
      });
      
      // Pre-cache data assets in background
      self.caches.open(DATA_CACHE_NAME).then(cache => {
        DATA_ASSETS.forEach(url => {
          fetch(url)
            .then(response => {
              if (response.ok) {
                return cache.put(url, response);
              }
            })
            .catch(err => {
              console.warn(`[ServiceWorker] Failed to cache data asset ${url}:`, err);
            });
        });
      });
      
      // Take control of all pages immediately
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // For same-origin requests
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }
        
        return fetch(event.request)
          .then(response => {
            // Don't cache if not a success response
            if (!response || response.status !== 200) {
              return response;
            }
            
            // Clone the response
            const responseToCache = response.clone();
            
            // Determine which cache to use
            const isDataAsset = DATA_ASSETS.some(asset => 
              url.pathname.includes(asset.replace('./', ''))
            );
            const cacheToUse = isDataAsset ? DATA_CACHE_NAME : CACHE_NAME;
            
            // Cache the response
            caches.open(cacheToUse).then(cache => {
              cache.put(event.request, responseToCache);
            });
            
            return response;
          })
          .catch(error => {
            console.log('[ServiceWorker] Network fetch failed:', error);
            
            // For HTML pages, return the cached index.html
            if (event.request.headers.get('accept').includes('text/html')) {
              return caches.match('./index.html');
            }
            
            // For other resources, you might want to return a fallback
            throw error;
          });
      })
    );
    return;
  }
  
  // For CDN/external requests
  if (CDN_ASSETS.some(cdnUrl => event.request.url.startsWith(cdnUrl))) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        // Return cached version if available
        if (cachedResponse) {
          return cachedResponse;
        }
        
        // Otherwise fetch from network
        return fetch(event.request)
          .then(response => {
            // Don't cache if not successful
            if (!response || response.status !== 200) {
              return response;
            }
            
            // Cache the response
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
            
            return response;
          })
          .catch(error => {
            console.log('[ServiceWorker] CDN fetch failed:', error);
            // For CDN failures, return nothing - let the app handle missing dependencies
            throw error;
          });
      })
    );
  }
  
  // For other external requests (like Google Fonts)
  if (event.request.url.startsWith('https://fonts.googleapis.com') || 
      event.request.url.startsWith('https://fonts.gstatic.com')) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        if (cachedResponse) {
          return cachedResponse;
        }
        
        return fetch(event.request)
          .then(response => {
            const responseToCache = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, responseToCache);
            });
            return response;
          })
          .catch(error => {
            console.log('[ServiceWorker] Font fetch failed:', error);
            throw error;
          });
      })
    );
  }
});
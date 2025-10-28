/**
 * Service Worker for Disaster Alert System PWA
 * Provides offline functionality with cache-first strategy for static assets
 * and network-first for API data
 */

// Cache version - increment when assets change to force refresh
const CACHE_VERSION = 'v1.2.0'; // Updated: Force cache invalidation on mobile devices
const STATIC_CACHE = `disaster-alert-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `disaster-alert-dynamic-${CACHE_VERSION}`;
const API_CACHE = `disaster-alert-api-${CACHE_VERSION}`;

// Static assets to cache immediately on install
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/static/css/main.css',
  '/static/js/main.js',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  // Leaflet assets
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
  'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
  // Google Fonts
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap'
];

// API endpoints to cache for offline access
const API_ENDPOINTS = [
  '/api/reports',
  '/api/public-data/all',
  '/api/public-data/wildfires',
  '/api/public-data/weather-alerts',
  '/api/cache/status'
];

// Maximum cache age for API data (15 minutes)
const API_CACHE_MAX_AGE = 15 * 60 * 1000;

/**
 * Install event - cache static assets
 */
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');

  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[Service Worker] Caching static assets');
        // Cache static assets individually to prevent one failure from blocking all
        return Promise.allSettled(
          STATIC_ASSETS.map(url => {
            return cache.add(url).catch(err => {
              console.warn(`[Service Worker] Failed to cache ${url}:`, err);
            });
          })
        );
      })
      .then(() => {
        console.log('[Service Worker] Static assets cached successfully');
        // Force activation immediately
        return self.skipWaiting();
      })
      .catch((err) => {
        console.error('[Service Worker] Installation failed:', err);
      })
  );
});

/**
 * Activate event - cleanup old caches
 */
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');

  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            // Delete old cache versions
            if (cacheName.startsWith('disaster-alert-') &&
                cacheName !== STATIC_CACHE &&
                cacheName !== DYNAMIC_CACHE &&
                cacheName !== API_CACHE) {
              console.log('[Service Worker] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('[Service Worker] Activated successfully');
        // Take control of all pages immediately
        return self.clients.claim();
      })
  );
});

/**
 * Fetch event - implement caching strategies
 */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // API requests - network-first strategy with cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      networkFirstStrategy(request)
    );
    return;
  }

  // Static assets - cache-first strategy
  event.respondWith(
    cacheFirstStrategy(request)
  );
});

/**
 * Cache-first strategy for static assets
 * Try cache first, then network, then fallback
 */
async function cacheFirstStrategy(request) {
  try {
    // Try cache first
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('[Service Worker] Serving from cache:', request.url);
      return cachedResponse;
    }

    // Not in cache, fetch from network
    console.log('[Service Worker] Fetching from network:', request.url);
    const networkResponse = await fetch(request);

    // Cache successful responses
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(DYNAMIC_CACHE);
      cache.put(request, networkResponse.clone());
    }

    return networkResponse;
  } catch (error) {
    console.error('[Service Worker] Cache-first strategy failed:', error);

    // Return offline page or basic fallback
    return new Response(
      JSON.stringify({
        error: 'Offline',
        message: 'Unable to fetch resource. Please check your connection.'
      }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}

/**
 * Network-first strategy for API requests
 * Try network first, then cache, with cache age validation
 */
async function networkFirstStrategy(request) {
  try {
    // Try network first
    console.log('[Service Worker] Fetching API from network:', request.url);
    const networkResponse = await fetch(request);

    // Cache successful API responses
    if (networkResponse && networkResponse.status === 200) {
      const cache = await caches.open(API_CACHE);
      const responseToCache = networkResponse.clone();

      // Add timestamp to track cache age
      const headers = new Headers(responseToCache.headers);
      headers.set('sw-cached-at', Date.now().toString());

      const cachedResponse = new Response(responseToCache.body, {
        status: responseToCache.status,
        statusText: responseToCache.statusText,
        headers: headers
      });

      cache.put(request, cachedResponse);
    }

    return networkResponse;
  } catch (error) {
    console.log('[Service Worker] Network failed, trying cache:', request.url);

    // Network failed, try cache
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
      // Check cache age
      const cachedAt = cachedResponse.headers.get('sw-cached-at');
      const age = cachedAt ? Date.now() - parseInt(cachedAt) : Infinity;

      if (age < API_CACHE_MAX_AGE) {
        console.log('[Service Worker] Serving fresh cached API data:', request.url);

        // Add offline indicator header
        const headers = new Headers(cachedResponse.headers);
        headers.set('X-Offline-Cache', 'true');
        headers.set('X-Cache-Age-Ms', age.toString());

        const offlineResponse = new Response(cachedResponse.body, {
          status: cachedResponse.status,
          statusText: cachedResponse.statusText,
          headers: headers
        });

        return offlineResponse;
      } else {
        console.warn('[Service Worker] Cached API data is stale:', request.url);
      }
    }

    // No cache available or too old
    return new Response(
      JSON.stringify({
        error: 'Offline',
        message: 'Unable to fetch disaster data. Please check your connection.',
        cached_at: null,
        offline: true
      }),
      {
        status: 503,
        statusText: 'Service Unavailable',
        headers: {
          'Content-Type': 'application/json',
          'X-Offline-Cache': 'unavailable'
        }
      }
    );
  }
}

/**
 * Background sync event - sync data when connection restored
 */
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync triggered:', event.tag);

  if (event.tag === 'sync-disaster-data') {
    event.waitUntil(
      syncDisasterData()
    );
  }
});

/**
 * Sync disaster data in background
 */
async function syncDisasterData() {
  try {
    console.log('[Service Worker] Syncing disaster data...');

    // Fetch latest data from all API endpoints
    const syncPromises = API_ENDPOINTS.map(endpoint => {
      return fetch(endpoint)
        .then(response => {
          if (response.ok) {
            return caches.open(API_CACHE).then(cache => {
              cache.put(endpoint, response.clone());
            });
          }
        })
        .catch(err => {
          console.warn(`[Service Worker] Failed to sync ${endpoint}:`, err);
        });
    });

    await Promise.allSettled(syncPromises);
    console.log('[Service Worker] Data sync completed');
  } catch (error) {
    console.error('[Service Worker] Background sync failed:', error);
  }
}

/**
 * Message event - handle commands from main thread
 */
self.addEventListener('message', (event) => {
  console.log('[Service Worker] Message received:', event.data);

  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }

  if (event.data && event.data.type === 'CACHE_STATUS') {
    event.ports[0].postMessage({
      version: CACHE_VERSION,
      caches: [STATIC_CACHE, DYNAMIC_CACHE, API_CACHE]
    });
  }

  if (event.data && event.data.type === 'CLEAR_CACHE') {
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName.startsWith('disaster-alert-')) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      event.ports[0].postMessage({ success: true });
    });
  }
});

console.log('[Service Worker] Loaded successfully');

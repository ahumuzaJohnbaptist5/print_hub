const CACHE_NAME = 'printhub-v3';
const urlsToCache = [
    '/',
    '/static/manifest.json',
    '/static/icons/icon.svg',
];

self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => Promise.all(
            keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
        ))
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request).then(response => response || fetch(event.request))
    );
});

// Push notification listener
self.addEventListener('push', event => {
    let data = {};
    if (event.data) {
        try {
            data = event.data.json();
        } catch(e) {
            data = {
                title: 'PrintHub',
                body: event.data.text(),
                icon: '/static/icons/icon.svg'
            };
        }
    }
    
    const options = {
        body: data.body || 'You have a new notification',
        icon: data.icon || '/static/icons/icon.svg',
        badge: '/static/icons/icon.svg',
        vibrate: [200, 100, 200],
        data: {
            url: data.url || '/'
        },
        actions: [
            { action: 'open', title: 'Open' },
            { action: 'close', title: 'Dismiss' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(
            data.title || 'PrintHub',
            options
        )
    );
});

// Notification click handler
self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    const url = event.notification.data.url || '/';
    
    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(clientsList => {
            for (let client of clientsList) {
                if (client.url.includes(url) && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});

// Push subscription change
self.addEventListener('pushsubscriptionchange', event => {
    event.waitUntil(
        self.registration.pushManager.subscribe(event.oldSubscription.options)
            .then(subscription => {
                // Send new subscription to server
                return fetch('/notifications/push/subscribe/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(subscription)
                });
            })
    );
});

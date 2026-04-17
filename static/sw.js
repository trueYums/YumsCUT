/**
 * Service Worker — handles Web Push notifications.
 * Compatible Safari iOS 16.4+, Chrome, Firefox.
 */

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener("push", (event) => {
  if (!event.data) return;

  let data;
  try {
    data = event.data.json();
  } catch {
    data = { title: "YouTube → TikTok", body: event.data.text() };
  }

  const title = data.title || "YouTube → TikTok";
  const options = {
    body: data.body || "",
    icon: "/static/icon.png",
    badge: "/static/icon.png",
    vibrate: [200, 100, 200],
    tag: "yt-tiktok",
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((list) => {
        for (const client of list) {
          if ("focus" in client) return client.focus();
        }
        if (clients.openWindow) return clients.openWindow("/");
      })
  );
});

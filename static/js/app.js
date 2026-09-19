// UniCA Sport Notifier - PWA & Web Push Script

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// Configuration HTMX pour le CSRF
document.addEventListener('htmx:configRequest', (event) => {
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) {
    event.detail.headers['X-CSRFToken'] = csrftoken;
  }
});

// Enregistrement du Service Worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then((reg) => {
        console.log('[PWA] Service Worker enregistré avec scope:', reg.scope);
      })
      .catch((err) => {
        console.error('[PWA] Échec enregistrement Service Worker:', err);
      });
  });
}

// Fonction globale d'abonnement WebPush
async function subscribeUserToPush() {
  const statusEl = document.getElementById('push-status-msg');
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    alert("Les notifications Push ne sont pas supportées par votre navigateur.");
    return;
  }

  try {
    if (statusEl) statusEl.textContent = "Demande d'autorisation...";
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      if (statusEl) statusEl.textContent = "Autorisation refusée par l'utilisateur.";
      alert("Permission de notification refusée.");
      return;
    }

    if (statusEl) statusEl.textContent = "Récupération de la clé VAPID...";
    const vapidRes = await fetch('/notifications/push/vapid-key/');
    const vapidData = await vapidRes.json();
    if (!vapidData.publicKey) {
      alert("Clé VAPID publique non configurée sur le serveur.");
      return;
    }

    const reg = await navigator.serviceWorker.ready;
    const convertedKey = urlBase64ToUint8Array(vapidData.publicKey);

    const subscription = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: convertedKey
    });

    if (statusEl) statusEl.textContent = "Enregistrement de l'appareil sur le serveur...";
    const subRes = await fetch('/notifications/push/subscribe/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify(subscription.toJSON())
    });

    if (subRes.ok) {
      if (statusEl) statusEl.textContent = "✅ Notifications Push activées avec succès !";
      alert("Abonnement Push actif ! Vous recevrez désormais les alertes sur cet appareil.");
      window.location.reload();
    } else {
      if (statusEl) statusEl.textContent = "❌ Erreur lors de l'enregistrement de l'abonnement.";
    }
  } catch (err) {
    console.error("[Push] Erreur lors de la souscription:", err);
    if (statusEl) statusEl.textContent = `Erreur: ${err.message}`;
    alert(`Erreur d'activation : ${err.message}`);
  }
}

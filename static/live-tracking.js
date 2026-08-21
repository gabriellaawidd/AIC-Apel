// live-tracking.js
//
// Live GPS position tracking and dynamic re-routing for F2.
// Loaded alongside index.html.
//
// Design note: this file owns the tracking loop, the backend calls, and
// the re-route banner. It does NOT touch the map -- when the driver
// switches route it calls window.onRouteSwitched(geometry), which
// index.html implements, so the map-drawing code stays in one place.
//
// Geolocation requires a secure context. http://localhost counts as
// secure, so desktop development works; opening this page on a phone via
// a LAN IP will silently deny location until it's served over HTTPS.

let watchId = null;
let currentTrip = null;        // { id, endLat, endLng }
let lastPostedPosition = null; // { lat, lng, timestamp } -- for throttling
let pendingRerouteCheck = false;

const MIN_SECONDS_BETWEEN_POSTS = 30;
const MIN_METERS_MOVED_BETWEEN_POSTS = 100;

// ---------------------------------------------------------------
// Trip lifecycle
// ---------------------------------------------------------------

// Creates the backend trip session, then starts watching position.
// The destination is stored here because every later re-route check
// needs it and the browser is the only thing that knows the trip is
// still running.
async function startTrip(startLat, startLng, endLat, endLng, shelfLifeRefHours = 72) {
  const query = `start_lat=${startLat}&start_lng=${startLng}` +
                `&end_lat=${endLat}&end_lng=${endLng}` +
                `&shelf_life_ref_hours=${shelfLifeRefHours}`;

  let data;
  try {
    data = await fetch(`/trip/create?${query}`, { method: "POST" }).then(r => r.json());
  } catch (err) {
    showTrackingStatus(`Could not start trip: ${err}`, "error");
    return null;
  }

  if (data.error) {
    showTrackingStatus(`Could not start trip: ${data.error}`, "error");
    return null;
  }

  currentTrip = { id: data.trip_id, endLat: endLat, endLng: endLng };
  lastPostedPosition = null;

  showTrackingStatus(
    `Trip started. Baseline: ${data.original_projected_freshness_pct}% freshness at delivery, ` +
    `${(data.original_duration_seconds / 3600).toFixed(1)}h planned.`,
    "ok"
  );

  startTracking(currentTrip.id);
  return data;
}

function startTracking(tripId) {
  if (!currentTrip) {
    currentTrip = { id: tripId, endLat: null, endLng: null };
  }

  if (!navigator.geolocation) {
    showTrackingStatus(
      "This browser has no Geolocation support, so live tracking is unavailable.",
      "error"
    );
    return;
  }

  watchId = navigator.geolocation.watchPosition(
    onPositionUpdate,
    onPositionError,
    {
      enableHighAccuracy: true,
      maximumAge: 10000,   // accept a cached position up to 10s old
      timeout: 15000,
    }
  );
}

function stopTracking() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
  currentTrip = null;
  lastPostedPosition = null;
  pendingRerouteCheck = false;
  hideBanner("reroute-banner");
  showTrackingStatus("Tracking stopped.", "info");
}

// ---------------------------------------------------------------
// Position reporting
// ---------------------------------------------------------------

function shouldPostPosition(lat, lng) {
  if (!lastPostedPosition) return true;

  const secondsSinceLastPost = (Date.now() - lastPostedPosition.timestamp) / 1000;
  if (secondsSinceLastPost >= MIN_SECONDS_BETWEEN_POSTS) return true;

  const distanceMeters = haversineMeters(
    lastPostedPosition.lat, lastPostedPosition.lng, lat, lng
  );
  return distanceMeters >= MIN_METERS_MOVED_BETWEEN_POSTS;
}

// Same formula as haversine_km() in main.py, in meters -- the backend
// and frontend should not disagree about how far the truck has moved.
function haversineMeters(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const toRad = deg => deg * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function onPositionUpdate(position) {
  if (!currentTrip) return;

  const { latitude, longitude, accuracy } = position.coords;

  if (!shouldPostPosition(latitude, longitude)) {
    return;
  }
  lastPostedPosition = { lat: latitude, lng: longitude, timestamp: Date.now() };

  const query = `lat=${latitude}&lng=${longitude}&accuracy_m=${accuracy || 0}`;

  fetch(`/trip/${currentTrip.id}/position?${query}`, { method: "POST" })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        showTrackingStatus(`Position rejected: ${data.error}`, "error");
        return;
      }

      showTrackingStatus(
        `Tracking: ${data.position_count} fix(es). ` +
        (data.current_projected_freshness_pct !== undefined
          ? `Projected ${data.current_projected_freshness_pct}% at delivery ` +
            `(planned ${data.original_projected_freshness_pct}%).`
          : "Next drift check pending."),
        "ok"
      );

      // One check at a time -- watchPosition can fire while the previous
      // MapKit alternatives lookup is still in flight, and two overlapping
      // banners is worse than a slightly stale one.
      if (data.reroute_suggested && !pendingRerouteCheck) {
        pendingRerouteCheck = true;
        checkForBetterRoute(latitude, longitude, currentTrip.endLat,
                            currentTrip.endLng, currentTrip.id, data);
      }
    })
    .catch(err => {
      console.error("Failed to post position update:", err);
      showTrackingStatus("Lost contact with the server; retrying on next fix.", "error");
    });
}

function onPositionError(err) {
  // 1 = PERMISSION_DENIED, 2 = POSITION_UNAVAILABLE, 3 = TIMEOUT.
  // Each needs different wording because each needs a different fix.
  let message;
  switch (err.code) {
    case 1:
      message = "Location permission denied. Allow location access for this site, " +
                "then start the trip again.";
      break;
    case 2:
      message = "Location unavailable right now — the device can't get a fix. " +
                "Tracking continues and will recover automatically.";
      break;
    case 3:
      message = "Timed out waiting for a location fix. Tracking continues.";
      break;
    default:
      message = `Geolocation error: ${err.message}`;
  }
  showTrackingStatus(message, err.code === 1 ? "error" : "warn");
  console.error("Geolocation error:", err.code, err.message);
}

// ---------------------------------------------------------------
// Re-route alternatives -- only fetched when the backend's
// /trip/{id}/position response signals reroute_suggested: true.
// ---------------------------------------------------------------

function checkForBetterRoute(currentLat, currentLng, endLat, endLng, tripId, verdict) {
  if (typeof mapkit === "undefined") {
    console.warn("MapKit JS not loaded -- cannot fetch route alternatives");
    showRerouteWarningOnly(verdict);
    pendingRerouteCheck = false;
    return;
  }
  if (endLat === null || endLng === null) {
    console.warn("Trip destination unknown -- cannot fetch alternatives");
    showRerouteWarningOnly(verdict);
    pendingRerouteCheck = false;
    return;
  }

  const directions = new mapkit.Directions();
  const request = {
    origin: new mapkit.Coordinate(currentLat, currentLng),
    destinations: [new mapkit.Coordinate(endLat, endLng)],
    transportType: mapkit.TransportType.Automobile,
    alternatives: true,
    // TODO: confirm "alternatives" is the correct MapKit JS 6 option
    // name against current docs -- same API-shape risk already flagged
    // for directions.eta() elsewhere in this project.
  };

  const handle = (error, data) => {
    if (error || !data || !data.routes || !data.routes.length) {
      console.warn("MapKit alternatives unavailable:", error);
      showRerouteWarningOnly(verdict);
      pendingRerouteCheck = false;
      return;
    }

    const candidates = data.routes.map(r => ({
      geometry: r.path.map(c => [c.latitude, c.longitude]),
      eta_seconds: r.expectedTravelTime,
    }));

    fetch(`/trip/${tripId}/evaluate-alternatives`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        alternatives: candidates,
        current_lat: currentLat,
        current_lng: currentLng,
      }),
    })
      .then(r => r.json())
      .then(ranked => renderRerouteOptions(ranked, verdict))
      .catch(err => {
        console.error("Failed to evaluate alternatives:", err);
        showRerouteWarningOnly(verdict);
      })
      .finally(() => { pendingRerouteCheck = false; });
  };

  try {
    // Same Promise-or-callback ambiguity as directions.eta() -- handle both.
    const maybePromise = directions.route(request, handle);
    if (maybePromise && typeof maybePromise.then === "function") {
      maybePromise.then(data => handle(null, data)).catch(error => handle(error, null));
    }
  } catch (err) {
    console.error("mapkit.Directions.route failed:", err);
    showRerouteWarningOnly(verdict);
    pendingRerouteCheck = false;
  }
}

// Shown when the backend says the trip has drifted but no alternatives
// could be fetched. The warning is still real and worth surfacing --
// silently swallowing it would hide a genuine problem from the driver.
function showRerouteWarningOnly(verdict) {
  if (!verdict) return;
  showBanner("reroute-banner", "warn", `
    <strong>Trip is drifting from plan</strong>
    <div class="banner-detail">${describeTriggers(verdict)}</div>
    <div class="banner-detail">No alternative routes available to compare right now.</div>
  `);
}

function describeTriggers(verdict) {
  const parts = [];
  if ((verdict.triggers || []).includes("freshness_drift")) {
    parts.push(
      `freshness projected at ${verdict.current_projected_freshness_pct}% ` +
      `vs ${verdict.original_projected_freshness_pct}% planned ` +
      `(${verdict.freshness_drift_pct} points worse)`
    );
  }
  if ((verdict.triggers || []).includes("eta_drift")) {
    parts.push(`running ${verdict.eta_drift_pct}% longer than planned`);
  }
  return parts.join(" · ") || "drift detected";
}

function renderRerouteOptions(ranked, verdict) {
  if (ranked.error) {
    showRerouteWarningOnly(verdict);
    return;
  }

  const current = ranked.current_route;
  const best = (ranked.alternatives || [])[0];

  // "No better option found" is a normal outcome, not a broken banner.
  if (!best || !current || best.projected_freshness_pct <= current.projected_freshness_pct) {
    showBanner("reroute-banner", "warn", `
      <strong>Trip is drifting from plan</strong>
      <div class="banner-detail">${describeTriggers(verdict)}</div>
      <div class="banner-detail">Checked ${(ranked.alternatives || []).length} alternative(s) — none is better than the current route.</div>
      <button type="button" onclick="hideBanner('reroute-banner')">Dismiss</button>
    `);
    return;
  }

  const freshnessDelta = best.freshness_delta_pct;
  const minutesDelta = Math.round((best.eta_delta_seconds || 0) / 60);
  const timeWord = minutesDelta === 0
    ? "same travel time"
    : `${Math.abs(minutesDelta)} min ${minutesDelta > 0 ? "longer" : "shorter"}`;

  window._bestAlternative = best;   // handed to acceptAlternative() on click

  showBanner("reroute-banner", "action", `
    <strong>Better route found: +${freshnessDelta}% freshness, ${timeWord}</strong>
    <div class="banner-detail">${describeTriggers(verdict)}</div>
    <div class="banner-detail">
      Alternative projects ${best.projected_freshness_pct}% freshness at delivery
      vs ${current.projected_freshness_pct}% on the current route.
    </div>
    <button type="button" onclick="acceptAlternative()">Switch route</button>
    <button type="button" onclick="hideBanner('reroute-banner')">Keep current</button>
  `);
}

function acceptAlternative() {
  const best = window._bestAlternative;
  if (!best || !currentTrip) return;

  fetch(`/trip/${currentTrip.id}/accept-alternative`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ geometry: best.geometry }),
  })
    .then(r => r.json())
    .then(() => {
      hideBanner("reroute-banner");
      showTrackingStatus("Switched to the alternative route.", "ok");
      // The map lives in index.html; let it redraw if it wants to.
      if (typeof window.onRouteSwitched === "function") {
        window.onRouteSwitched(best.geometry);
      }
    })
    .catch(err => console.error("Failed to accept alternative:", err));
}

// ---------------------------------------------------------------
// Small DOM helpers. index.html supplies #banners and #tracking-status.
// ---------------------------------------------------------------

function showBanner(id, kind, html) {
  const host = document.getElementById("banners");
  if (!host) return;

  let el = document.getElementById(id);
  if (!el) {
    el = document.createElement("div");
    el.id = id;
    host.appendChild(el);
  }
  el.className = `banner banner-${kind}`;
  el.innerHTML = html;
  el.hidden = false;
}

function hideBanner(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = true;
}

function showTrackingStatus(message, kind = "info") {
  const el = document.getElementById("tracking-status");
  if (!el) return;
  el.textContent = message;
  el.className = `tracking-status tracking-${kind}`;
}

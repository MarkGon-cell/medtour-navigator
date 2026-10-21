/**
 * One shared "where is the patient?" reader, used by both routes that need a
 * position.
 *
 * Two stages on purpose, because a phone is not a desktop. The snippet
 * everyone copies from MDN issues a single `enableHighAccuracy: true`
 * request: on a desktop that returns from Wi-Fi/ARP location in well under a
 * second, but on an Android phone it waits for a satellite fix that
 * routinely outlives the 8-second budget it was given -- and the caller then
 * falls back to the default coordinates while the phone was perfectly
 * capable of locating it. So we ask for the cheap sources first (a recent
 * cache, then Wi-Fi/cell), and only spend the long GPS budget if those come
 * back empty. A denied permission short-circuits: a second request cannot
 * change the user's answer.
 *
 * Everything here RESOLVES with either a position or an error instead of
 * throwing, because `GeolocationPositionError` is a plain object, not an
 * Error -- a `catch {}` around this API silently swallows every failure.
 */

export type GeolocationOutcome = GeolocationPosition | GeolocationPositionError;

// A recent fix is a perfectly good starting point and costs zero seconds:
// phones hand these out constantly as the user moves around.
const NETWORK_FIX: PositionOptions = {
  enableHighAccuracy: false,
  timeout: 8000,
  maximumAge: 5 * 60 * 1000,
};

// Only used when the cheap answer was unavailable -- here a longer wait is
// the right trade, since the alternative is sending the patient's searches
// out with someone else's coordinates.
const GPS_FIX: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 20_000,
  maximumAge: 0,
};

export function isPosition(outcome: GeolocationOutcome): outcome is GeolocationPosition {
  return typeof (outcome as GeolocationPosition | undefined)?.coords?.latitude === "number";
}

/** One actionable sentence for a failed fix, or undefined if we can't say. */
export function describeGeolocationFailure(
  error: GeolocationPositionError | undefined,
  retryHint = "Tap the blue pin to try again.",
): string | undefined {
  if (!error) return undefined;
  if (error.message?.startsWith("Only secure origins are allowed")) {
    // Chromium (since Chrome 50) refuses the API outright on plain HTTP.
    return "Location is blocked on a plain HTTP address. Open the site over https:// or http://localhost to use GPS.";
  }
  if (error.code === 1) {
    return "Location permission was blocked. Allow it in the address bar to find nearby ERs.";
  }
  if (error.code === 3) {
    return `Finding your location took too long. ${retryHint}`;
  }
  if (error.code === 2) {
    // Android lands here whenever the Location toggle (or Google Location
    // Accuracy) is off -- nothing on the page can fix that, so say it.
    return `Your device couldn't get a location fix. Turn on Location in the quick settings. ${retryHint}`;
  }
  return `Couldn't read your location. ${retryHint}`;
}

/** Never rejects: success and failure both come back as a resolved value. */
export async function readPosition(): Promise<GeolocationOutcome> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return {
      code: 2,
      message: "This browser has no Geolocation API.",
      PERMISSION_DENIED: 1,
      POSITION_UNAVAILABLE: 2,
      TIMEOUT: 3,
    } as GeolocationPositionError;
  }

  const ask = (options: PositionOptions) =>
    new Promise<GeolocationOutcome>((resolve) => {
      navigator.geolocation.getCurrentPosition(resolve, resolve, options);
    });

  const network = await ask(NETWORK_FIX);
  if (isPosition(network)) return network;
  if (network.code === 1) return network; // denied -- asking again won't help
  return ask(GPS_FIX);
}

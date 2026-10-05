/**
 * content.js
 *
 * Content script injected into youtube.com/watch pages.
 * This is registered as a backup/direct injection target.
 * 
 * Primary control happens via background.js executeScript.
 * This file logs readiness for debugging.
 */

(function() {
  if (window.__ytgc_loaded) return;
  window.__ytgc_loaded = true;
  console.log("[YTGC] Content script loaded on", window.location.href);
})();

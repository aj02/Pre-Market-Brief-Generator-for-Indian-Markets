// Ticker enhancement: pause on visibility change, restart on focus.
// Animation itself is CSS-driven (see newspaper.css).
(function () {
  const track = document.querySelector(".ticker-track");
  if (!track) return;

  document.addEventListener("visibilitychange", () => {
    track.style.animationPlayState = document.hidden ? "paused" : "running";
  });
})();

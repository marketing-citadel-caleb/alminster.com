/* alminster.com: theme toggle, email reveal, click-to-play players. */
(function () {
  "use strict";
  var root = document.documentElement;

  // Theme: follows the device setting until someone picks one.
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    var mode = function () {
      return root.dataset.theme ||
        (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    };
    var sync = function () {
      var m = mode();
      toggle.dataset.mode = m;
      toggle.setAttribute("aria-label", m === "dark" ? "Switch to light mode" : "Switch to dark mode");
    };
    toggle.addEventListener("click", function () {
      var next = mode() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch (e) { /* private mode */ }
      sync();
    });
    sync();
    toggle.hidden = false;
  }

  // Email: rebuilt here so the address never sits in the page source.
  document.querySelectorAll("[data-e]").forEach(function (el) {
    var address = atob(el.dataset.e).split("").reverse().join("");
    el.href = "mailto:" + address;
    if (el.hasAttribute("data-show-address")) el.textContent = address;
  });
  document.querySelectorAll("[data-needs-js]").forEach(function (el) { el.hidden = false; });

  // Players load only when tapped, which keeps the page fast.
  function play(host, src, title) {
    var frame = document.createElement("iframe");
    frame.src = src;
    frame.title = title;
    frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    frame.allowFullscreen = true;
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    host.replaceChildren(frame);
  }

  document.querySelectorAll("[data-embed]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      play(link.closest(".player"), link.dataset.embed, link.dataset.title);
    });
  });

  document.querySelectorAll("[data-twitch]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      var host = document.getElementById("player");
      if (!host) return;
      event.preventDefault();
      play(host, "https://player.twitch.tv/?channel=" + encodeURIComponent(link.dataset.twitch) +
        "&parent=" + location.hostname + "&autoplay=true", "Alminster of Azeroth on Twitch");
      host.scrollIntoView({ block: "nearest" });
    });
  });
})();

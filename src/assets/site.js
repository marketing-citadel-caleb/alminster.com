/* alminster.com: theme toggle, email reveal, click-to-play players, live ticker. */
(function () {
  "use strict";
  var root = document.documentElement;

  function mode() {
    return root.dataset.theme ||
      (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  }

  // Live market ticker (TradingView). Loads only once it scrolls near the
  // screen, so it never slows down the first view of the page.
  var ticker = document.querySelector("[data-ticker]");
  var tickerLoaded = false;
  function loadTicker() {
    var config = JSON.parse(ticker.dataset.ticker);
    config.colorTheme = mode();
    var widget = document.createElement("div");
    widget.className = "tradingview-widget-container__widget";
    var script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
    script.async = true;
    script.textContent = JSON.stringify(config);
    ticker.replaceChildren(widget, script);
    tickerLoaded = true;
  }
  if (ticker && "IntersectionObserver" in window) {
    var watcher = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        watcher.disconnect();
        loadTicker();
      }
    }, { rootMargin: "400px 0px" });
    watcher.observe(ticker);
  }

  // Theme: follows the device setting until someone picks one.
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
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
      if (tickerLoaded) loadTicker(); // redraw in the new colors
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

  // "Updated" stamps: show how long ago, which stays true however long the page has been open.
  function ago(then) {
    var minutes = Math.round((Date.now() - then) / 60000);
    if (minutes < 2) return "just now";
    if (minutes < 60) return minutes + " minutes ago";
    var hours = Math.round(minutes / 60);
    if (hours < 24) return hours === 1 ? "about an hour ago" : hours + " hours ago";
    return null; // over a day old: keep the printed date
  }
  function refreshStamps() {
    document.querySelectorAll("time[data-ago]").forEach(function (el) {
      var then = Date.parse(el.dateTime);
      var label = isNaN(then) ? null : ago(then);
      if (label) {
        if (!el.title) el.title = el.textContent;
        el.textContent = label;
      }
    });
  }
  refreshStamps();
  setInterval(refreshStamps, 60000);

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

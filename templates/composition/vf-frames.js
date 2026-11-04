/*
 * The provisional composition of video-factory: every visible state is a function of the frame number.
 *
 * HyperFrames seeks each frame on its own and announces it with an "hf-seek" event; this script turns the time into a
 * frame number and draws that frame from the data `compose` wrote into the page (#vf-data): the word captions, the
 * full-frame shots, the punch-ins. No GSAP, no timer, no Date, no randomness: the same frame number always gives the
 * same page. `compose` writes the shot containers and their media into the page; this script only fills the text and
 * sets, frame by frame, what shows. The look is provisional (one font, white text, black shots) until the video design
 * system replaces it.
 */
(function () {
  "use strict";

  var data = JSON.parse(document.getElementById("vf-data").textContent);
  var FONT = '"VF Provisoire"';
  var CAPTION_SIZE = 112;
  var built = false;
  var last = 0;
  var items = {};
  var measure = document.createElement("canvas").getContext("2d");

  function width(text, size) {
    measure.font = "700 " + size + "px " + FONT;
    return measure.measureText(text).width;
  }

  /* The largest size up to `size` at which the text holds on one line of `room` pixels. */
  function fit(text, size, room) {
    var found = width(text, size);
    return found <= room ? size : Math.max(8, Math.floor((size * room) / found));
  }

  function line(text, size, align) {
    var el = document.createElement("div");
    el.className = "vf-text";
    el.textContent = text;
    el.style.fontSize = size + "px";
    el.style.textAlign = align || "center";
    return el;
  }

  function buildShot(shot, index) {
    var area = document.querySelector("#shot-" + index + " .vf-area");
    var room = data.shot.width - 8;
    var made = [];
    if (shot.kind === "stat") {
      made.push(line(shot.parts[0], fit(shot.parts[0], 240, room)));
      if (shot.parts.length > 1) made.push(line(shot.parts.slice(1).join(" "), 72));
    } else if (shot.kind === "etapes") {
      var size = Math.min(84, Math.floor((data.shot.height - 40 * shot.parts.length) / (1.25 * shot.parts.length)));
      shot.parts.forEach(function (step) {
        made.push(line(step, fit(step, size, room)));
      });
    } else if (shot.kind === "code") {
      var code = line("", 64, "left");
      code.style.whiteSpace = "pre-wrap";
      code.style.overflowWrap = "anywhere";
      made.push(code);
    }
    made.forEach(function (el) {
      area.appendChild(el);
    });
    items[index] = made;
  }

  function build() {
    data.words.forEach(function (w) {
      w.size = fit(w.text, CAPTION_SIZE, data.caption.width - 8);
    });
    data.shots.forEach(buildShot);
    built = true;
  }

  function ease(progress) {
    var p = Math.min(1, Math.max(0, progress));
    return 1 - Math.pow(1 - p, 3);
  }

  function drawShot(shot, index, frame) {
    var layer = document.getElementById("shot-" + index);
    var active = frame >= shot.start && frame < shot.end;
    layer.style.visibility = active ? "visible" : "hidden";
    if (!active) return;
    var local = frame - shot.start;
    var span = shot.end - shot.start;
    var made = items[index] || [];
    if (shot.kind === "stat") {
      var grow = ease(local / 8);
      made.forEach(function (el) {
        el.style.opacity = String(grow);
        el.style.transform = "scale(" + (0.9 + 0.1 * grow) + ")";
      });
    } else if (shot.kind === "etapes") {
      var every = Math.max(1, Math.floor((0.7 * span) / Math.max(1, made.length)));
      made.forEach(function (el, k) {
        el.style.opacity = String(ease((local - k * every) / 6));
      });
    } else if (shot.kind === "code") {
      var text = shot.parts.join(" | ");
      var shown = Math.min(text.length, Math.floor((text.length * local) / Math.max(1, 0.6 * span)) + 1);
      made[0].textContent = text.slice(0, shown);
    } else if (shot.kind === "capture" && shot.still) {
      var image = document.getElementById("capture-" + index);
      if (image) image.style.transform = "scale(" + (1 + 0.06 * (local / Math.max(1, span))) + ")";
    }
  }

  function drawCaption(frame) {
    var caption = document.getElementById("caption");
    var current = null;
    data.words.forEach(function (w) {
      if (frame >= w.start && frame < w.end) current = w;
    });
    caption.textContent = current ? current.text : "";
    caption.style.fontSize = (current ? current.size : CAPTION_SIZE) + "px";
  }

  function drawCamera(frame) {
    var camera = document.getElementById("camera-wrap");
    if (!camera) return;
    var scale = 1;
    data.zooms.forEach(function (zoom) {
      if (frame >= zoom.start && frame < zoom.end) scale = 1 + 0.12 * ease((frame - zoom.start + 1) / 4);
    });
    camera.style.transform = "scale(" + scale + ")";
  }

  function render(frame) {
    last = frame;
    drawCamera(frame);
    if (!built) return;
    data.shots.forEach(function (shot, index) {
      drawShot(shot, index, frame);
    });
    drawCaption(frame);
  }

  window.__hf = window.__hf || {};
  window.__hf.buildReady = window.__hf.buildReady || {};
  window.__hf.buildReady.vfFonts = document.fonts.load("700 " + CAPTION_SIZE + "px " + FONT).then(function () {
    build();
    render(last);
  });
  window.addEventListener("hf-seek", function (event) {
    render(Math.round(event.detail.time * data.fps));
  });
  render(0);
})();

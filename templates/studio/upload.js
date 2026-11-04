// The takes of a video, sent from Safari: each file is fingerprinted on the phone, then sent with its fingerprint,
// which the server checks on receipt. Once every take is in, the server runs vf ingest and the card goes to Montage.
(function () {
  "use strict";
  var form = document.getElementById("prises");
  if (!form) return;
  var input = form.querySelector("input[type=file]");
  var button = form.querySelector("button");
  var list = document.getElementById("suivi");
  var video = form.dataset.video;
  var SLICE = 8 * 1024 * 1024;

  function line(text) {
    var item = document.createElement("li");
    item.textContent = text;
    list.appendChild(item);
    return item;
  }

  function read(blob) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(new Uint8Array(reader.result)); };
      reader.onerror = function () { reject(reader.error); };
      reader.readAsArrayBuffer(blob);
    });
  }

  async function fingerprint(file, item) {
    var hash = new Sha256();
    for (var offset = 0; offset < file.size; offset += SLICE) {
      hash.update(await read(file.slice(offset, offset + SLICE)));
      item.textContent = file.name + " : empreinte " + Math.floor((100 * Math.min(file.size, offset + SLICE)) / file.size) + " %";
    }
    return hash.hex();
  }

  function send(file, index, digest, item) {
    return new Promise(function (resolve, reject) {
      var request = new XMLHttpRequest();
      request.open("PUT", "/v/" + video + "/prises/" + index);
      request.setRequestHeader("X-Empreinte", digest);
      request.setRequestHeader("X-Nom", encodeURIComponent(file.name));
      request.upload.onprogress = function (event) {
        if (event.lengthComputable) item.textContent = file.name + " : envoi " + Math.floor((100 * event.loaded) / event.total) + " %";
      };
      request.onload = function () {
        if (request.status === 200) resolve(JSON.parse(request.responseText));
        else reject(new Error(request.responseText || "HTTP " + request.status));
      };
      request.onerror = function () { reject(new Error("réseau coupé")); };
      request.send(file);
    });
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var files = Array.prototype.slice.call(input.files);
    if (!files.length) return;
    button.disabled = true;
    list.textContent = "";
    try {
      for (var i = 0; i < files.length; i++) {
        var item = line(files[i].name);
        var digest = await fingerprint(files[i], item);
        var stored = await send(files[i], i, digest, item);
        item.textContent = files[i].name + " : reçue, empreinte " + stored.sha256.slice(0, 12) + " (téléphone " + digest.slice(0, 12) + ")";
      }
      var done = line("vf ingest en cours…");
      var response = await fetch("/v/" + video + "/prises", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count: files.length }),
      });
      var result = await response.json();
      done.textContent = result.message;
      if (response.ok) window.setTimeout(function () { window.location.reload(); }, 1500);
      else button.disabled = false;
    } catch (error) {
      line("Échec : " + error.message);
      button.disabled = false;
    }
  });
})();

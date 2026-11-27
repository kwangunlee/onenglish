"use strict";
let trails, playerScope, gameSession, parentOrigin, pendingResult = null;

function send(type, fields = {}) {
  window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:"+type, ...fields}, parentOrigin || "*");
}

function sendResult(game, course) {
  pendingResult = {session:gameSession, round:game.id, course, attempts:game.attempts};
  send("setComponentValue", {dataType:"json", value:pendingResult});
}

function connectGame() {
  window.addEventListener("message", event => {
    if (event.source !== window.parent || event.data?.type !== "streamlit:render") return;
    if (parentOrigin && parentOrigin !== event.origin) return;
    parentOrigin = event.origin;
    const args = event.data.args;
    stamps = args.stamps;
    if (!trails) {
      trails = args.courses;
      playerScope = args.profile;
      gameSession = args.session;
      openTrail(0);
    } else if (pendingResult && args.saved === pendingResult.round) {
      pendingResult = null;
      renderNavigation();
      renderPhase();
    }
  });
  send("componentReady", {apiVersion:1});
  new ResizeObserver(() => send("setFrameHeight", {height:Math.ceil(document.body.getBoundingClientRect().height)+2}))
    .observe(document.body);
}

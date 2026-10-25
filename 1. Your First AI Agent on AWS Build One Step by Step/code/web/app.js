"use strict";
const cfg = window.AGENT_CONFIG;
const statusEl = document.getElementById("status");
const chat = document.getElementById("chat");
let accessToken = null; // In memory only; reload requires sign-in again.
let expiresAt = 0;
let sessionId = crypto.randomUUID();
let busy = false;
function message(who, text) {
  const p = document.createElement("p");
  p.textContent = `${who}: ${text}`; // Never inject user/model text through innerHTML.
  chat.appendChild(p); chat.scrollTop = chat.scrollHeight;
}
function randomUrlSafe(bytes = 32) {
  return b64url(crypto.getRandomValues(new Uint8Array(bytes)));
}
function b64url(bytes) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/g,"");
}
async function login() {
  if (!cfg) throw new Error("Generate config.js first");
  const verifier = randomUrlSafe();
  const state = randomUrlSafe();
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem("oauth", JSON.stringify({verifier, state, created:Date.now()}));
  const url = new URL(cfg.LoginDomain + "/oauth2/authorize");
  url.search = new URLSearchParams({response_type:"code",client_id:cfg.ClientId,
    redirect_uri:cfg.CallbackUrl,scope:"openid agent/chat",state,
    code_challenge_method:"S256",code_challenge:b64url(new Uint8Array(digest))});
  location.assign(url);
}
async function callback() {
  if (!cfg) throw new Error("Missing config.js: run scripts/configure_web.py");
  const params = new URLSearchParams(location.search);
  const code = params.get("code");
  if (params.has("error")) {
    history.replaceState(null,"",location.pathname);
    sessionStorage.removeItem("oauth");
    throw new Error("Sign-in was not completed; try again");
  }
  if (!code) {statusEl.textContent = "Sign in to start."; return;}
  const saved = JSON.parse(sessionStorage.getItem("oauth") || "null");
  sessionStorage.removeItem("oauth");
  history.replaceState(null,"",location.pathname);
  if (!saved || saved.state !== params.get("state") || Date.now()-saved.created>600000) {
    throw new Error("Invalid or expired login state. Sign in again.");
  }
  const response = await fetch(cfg.LoginDomain + "/oauth2/token", {method:"POST",
    headers:{"Content-Type":"application/x-www-form-urlencoded"},
    body:new URLSearchParams({grant_type:"authorization_code",client_id:cfg.ClientId,
      code,redirect_uri:cfg.CallbackUrl,code_verifier:saved.verifier})});
  if (!response.ok) throw new Error("Code exchange failed. Sign in again.");
  const tokens = await response.json();
  accessToken = tokens.access_token;
  expiresAt = Date.now() + tokens.expires_in*1000;
  // Do not persist tokens or log them. This lab deliberately does not refresh.
  statusEl.textContent = "Signed in. One request at a time; sign in again after expiry.";
}
document.getElementById("login").onclick = () => login().catch(e => statusEl.textContent=e.message);
document.getElementById("logout").onclick = () => {
  accessToken=null; expiresAt=0; sessionId=crypto.randomUUID(); chat.replaceChildren();
  sessionStorage.removeItem("oauth");
  if (cfg) {
    const u=new URL(cfg.LoginDomain+"/logout");
    u.search=new URLSearchParams({client_id:cfg.ClientId,logout_uri:cfg.CallbackUrl});
    location.assign(u);
  }
};
document.getElementById("new").onclick = () => {
  if (busy) return;
  sessionId=crypto.randomUUID(); chat.replaceChildren();
  statusEl.textContent="New conversation. Prior server memory expires after its TTL.";
};
document.getElementById("form").onsubmit = async event => {
  event.preventDefault();
  if (busy) return;
  if (!accessToken || Date.now()>=expiresAt) {statusEl.textContent="Sign in first or renew your expired login."; return;}
  const input=document.getElementById("message");
  const text=input.value.trim(); if (!text) return;
  busy=true; document.getElementById("send").disabled=true;
  message("You",text); input.value="";
  const aborter=new AbortController(); const timer=setTimeout(()=>aborter.abort(),28000);
  try {
    const r=await fetch(cfg.ApiBase+"/chat",{method:"POST",signal:aborter.signal,
      headers:{"Content-Type":"application/json","Authorization":"Bearer "+accessToken},
      body:JSON.stringify({message:text,session_id:sessionId})});
    const data=await r.json();
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    message("Agent",data.reply);
    statusEl.textContent=`Request ${data.request_id}; tokens ${data.usage.totalTokens || 0}`;
  } catch(e) {message("Error", e.name==="AbortError"?"Request timed out; the backend may still be finishing. Wait before retrying.":e.message);}
  finally {clearTimeout(timer); busy=false; document.getElementById("send").disabled=false;}
};
callback().catch(e=>statusEl.textContent=e.message);

import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { ROOT } from "./config.js";

// Shortcuts Jarvis may open on the computer it runs on. Edit config/apps.json
// to add more: { "name": { "url": "https://…" } } or { "name": { "command": "C:\\path\\app.exe" } }.
function loadApps() {
  try {
    return JSON.parse(fs.readFileSync(path.join(ROOT, "config", "apps.json"), "utf8"));
  } catch {
    return {};
  }
}

export const appNames = Object.keys(loadApps());

function isWebUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch {
    return false;
  }
}

// Open a URL with the OS default handler. Arguments are passed as an array
// (no shell), so characters like & in a URL can't be interpreted as commands.
function openUrl(url) {
  const [cmd, args] =
    process.platform === "win32"
      ? ["rundll32", ["url.dll,FileProtocolHandler", url]]
      : process.platform === "darwin"
        ? ["open", [url]]
        : ["xdg-open", [url]];
  return start(cmd, args);
}

// Resolve once the process has started; reject if it could not be launched.
function start(cmd, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { detached: true, stdio: "ignore" });
    child.once("spawn", () => {
      child.unref();
      resolve();
    });
    child.once("error", (err) => reject(new Error(`tidak bisa menjalankan ${cmd}: ${err.code || err.message}`)));
  });
}

/** Open a named shortcut from config/apps.json, or any http(s) URL. */
export async function openOnComputer(target) {
  const apps = loadApps();
  const key = target.trim().toLowerCase();
  const app = apps[key];
  if (app?.command) {
    await start(app.command, []);
    return `Membuka ${key}.`;
  }
  if (app?.url) {
    await openUrl(app.url);
    return `Membuka ${key} di browser.`;
  }
  if (isWebUrl(target.trim())) {
    await openUrl(target.trim());
    return `Membuka ${target.trim()} di browser.`;
  }
  return `"${target}" tidak ada di daftar pintasan (${Object.keys(apps).join(", ") || "kosong"}) dan bukan URL http/https.`;
}

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
export var AIO_DIR = join(homedir(), ".aio");
export var CONTEXT_FILE = join(AIO_DIR, "context.json");
export var DEFAULT_CONTEXT = { provider: "local" };
export function loadContext() {
  try {
    const raw = readFileSync(CONTEXT_FILE, "utf-8");
    const saved = JSON.parse(raw);
    return {
      provider: "local",
      apiUrl: saved.apiUrl
    };
  } catch {
    return DEFAULT_CONTEXT;
  }
}
export function resolveContext(flags) {
  const saved = loadContext();
  return {
    provider: "local",
    apiUrl: flags.apiUrl ?? saved.apiUrl
  };
}

import { Command } from "commander";
import source_default from "chalk";
import { AioClient, CliError } from "./client.js";
import { createBrowserCommand } from "./commands/browser.js";
import { createGuiCommand } from "./commands/gui.js";
import { createMcpCommand } from "./commands/mcp.js";
import { createSandboxCommand } from "./commands/sandbox.js";
import { createSkillsCommand } from "./commands/skills.js";
import { loadConfig, resolveApiUrl } from "./config.js";
import { loadContext, resolveContext } from "./context.js";
import { printError } from "./output.js";
export var program2 = new Command();
program2.name("aio").description("CLI for AIO Sandbox — browser, GUI, shell, file, skills, and MCP operations").version("0.3.12").addHelpText("after", () => {
  if (in_sandbox) return "";
  const ctx = loadContext();
  const target = `local (${ctx.apiUrl ?? "http://127.0.0.1:8080"})`;
  return `
${source_default.dim(`Current context: ${target}`)}`;
}).option("--api-url <url>", "Override API base URL").option("--output <format>", "Output format: json, table, text (default: auto-detect)").option("-v, --verbose", "Show request/response details").option("-q, --quiet", "Suppress non-essential output");
export function getGlobalOpts() {
  return program2.opts();
}
export var clientInstance = null;
export function getClient() {
  if (clientInstance) return clientInstance;
  throw new Error("Client not initialized");
}
var { in_sandbox } = await loadConfig();
program2.addCommand(createGuiCommand(getClient, getGlobalOpts));
program2.addCommand(createBrowserCommand(getClient, getGlobalOpts));
program2.addCommand(createSandboxCommand(getClient, getGlobalOpts, in_sandbox ?? false));
program2.addCommand(createMcpCommand(getClient, getGlobalOpts));
program2.addCommand(createSkillsCommand(getClient, getGlobalOpts));
export var SKIP_CLIENT_COMMANDS = /* @__PURE__ */ new Set(["use", "login", "logout", "update"]);
export var SANDBOX_MGMT_COMMANDS = /* @__PURE__ */ new Set(["create", "list", "ls", "stop", "rm", "remove", "logs", "status"]);
program2.hook("preAction", async (_thisCommand, actionCommand) => {
  const cmdName = actionCommand.name();
  const parentName = actionCommand.parent?.name();
  if (SKIP_CLIENT_COMMANDS.has(cmdName)) return;
  if (parentName === "sandbox" && SANDBOX_MGMT_COMMANDS.has(cmdName)) return;
  const flags = program2.opts();
  const ctx = resolveContext(flags);
  const apiUrl = await resolveApiUrl(ctx.apiUrl);
  clientInstance = new AioClient(apiUrl, flags.verbose !== void 0, void 0, void 0);
});
export async function main() {
  try {
    await program2.parseAsync(process.argv);
  } catch (err) {
    if (err instanceof CliError) {
      printError(err);
      process.exit(1);
    }
    throw err;
  }
}
main().catch((err) => {
  printError(err);
  process.exit(1);
});

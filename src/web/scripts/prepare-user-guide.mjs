import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(scriptDirectory, "..");
const guidePath = resolve(webRoot, "public", "ai4ms-user-guide.html");
const packagePath = resolve(webRoot, "package.json");
const requiredDeploymentLinks = new Map([
  ["workbench", "/"],
  ["health", "/healthz"],
  ["api-docs", "/docs"],
  ["guide", "/ai4ms-user-guide.html"],
]);

export function deploymentLinks(html) {
  return new Map(
    [...html.matchAll(/<a\b[^>]*\bdata-deploy-link="([^"]+)"[^>]*\bhref="([^"]+)"[^>]*>/g)]
      .map((match) => [match[1], match[2]]),
  );
}

export function validateDeploymentLinks(html) {
  const links = deploymentLinks(html);
  const errors = [];
  for (const [key, expectedPath] of requiredDeploymentLinks) {
    const href = links.get(key);
    if (!href) {
      errors.push(`missing deployment link: ${key}`);
      continue;
    }
    if (href !== expectedPath) {
      errors.push(`deployment link ${key} must be ${expectedPath}, received ${href}`);
    }
  }
  for (const [key, href] of links) {
    if (!href.startsWith("/") || href.startsWith("//") || href.includes("..")) {
      errors.push(`deployment link ${key} is unsafe: ${href}`);
    }
  }
  return errors;
}

export function injectBuildMetadata(html, metadata) {
  const replacements = [
    [
      /(<meta name="ai4ms-guide-version" content=")[^"]*(")/,
      `$1${metadata.version}$2`,
    ],
    [
      /(<meta name="ai4ms-guide-commit" content=")[^"]*(")/,
      `$1${metadata.commit}$2`,
    ],
    [
      /(<meta name="ai4ms-guide-channel" content=")[^"]*(")/,
      `$1${metadata.channel}$2`,
    ],
    [
      /(<strong data-ai4ms-build-field="version">)[^<]*(<\/strong>)/,
      `$1v${metadata.version} · ${metadata.channel}$2`,
    ],
    [
      /(<span data-ai4ms-build-field="commit">)[^<]*(<\/span>)/,
      `$1${metadata.commit}$2`,
    ],
    [
      /(<span data-ai4ms-build-field="footer">)[^<]*(<\/span>)/,
      `$1文档 v${metadata.version} · ${metadata.channel} · ${metadata.commit}$2`,
    ],
  ];
  return replacements.reduce((result, [pattern, replacement]) => {
    if (!pattern.test(result)) {
      throw new Error(`user guide build marker is missing: ${pattern}`);
    }
    return result.replace(pattern, replacement);
  }, html);
}

async function checkLiveDeployment(baseUrl, html) {
  const links = deploymentLinks(html);
  const failures = [];
  for (const [key, href] of links) {
    const target = new URL(href, baseUrl);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8_000);
    try {
      let response = await fetch(target, {
        method: "HEAD",
        redirect: "follow",
        signal: controller.signal,
      });
      if (response.status === 405) {
        response = await fetch(target, {
          method: "GET",
          redirect: "follow",
          signal: controller.signal,
        });
      }
      if (!response.ok) failures.push(`${key}: HTTP ${response.status} ${target}`);
    } catch (error) {
      failures.push(`${key}: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      clearTimeout(timer);
    }
  }
  if (failures.length) {
    throw new Error(`deployment link check failed:\n${failures.join("\n")}`);
  }
}

function gitCommit() {
  if (process.env.AI4MS_GIT_SHA) return process.env.AI4MS_GIT_SHA.slice(0, 12);
  if (process.env.GITHUB_SHA) return process.env.GITHUB_SHA.slice(0, 12);
  try {
    return execFileSync("git", ["rev-parse", "--short=12", "HEAD"], {
      cwd: webRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return "local-build";
  }
}

async function main() {
  const packageJson = JSON.parse(await readFile(packagePath, "utf8"));
  const metadata = {
    version: process.env.AI4MS_RELEASE_VERSION || packageJson.version,
    channel: process.env.AI4MS_RELEASE_CHANNEL || "ai4ms",
    commit: gitCommit(),
  };
  const source = await readFile(guidePath, "utf8");
  const prepared = injectBuildMetadata(source, metadata);
  const errors = validateDeploymentLinks(prepared);
  if (errors.length) throw new Error(errors.join("\n"));
  if (prepared !== source) await writeFile(guidePath, prepared, "utf8");

  if (process.argv.includes("--check-live")) {
    const baseUrl = process.env.AI4MS_DEPLOY_CHECK_URL;
    if (!baseUrl) {
      throw new Error("AI4MS_DEPLOY_CHECK_URL is required with --check-live");
    }
    await checkLiveDeployment(baseUrl, prepared);
  }
  process.stdout.write(
    `AI4MS guide v${metadata.version} (${metadata.channel}, ${metadata.commit}): ${requiredDeploymentLinks.size} deployment links valid\n`,
  );
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  await main();
}

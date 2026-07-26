import assert from "node:assert/strict";
import test from "node:test";

import {
  injectBuildMetadata,
  validateDeploymentLinks,
} from "./prepare-user-guide.mjs";

const links = `
  <a data-deploy-link="workbench" href="/">Workbench</a>
  <a data-deploy-link="health" href="/healthz">Health</a>
  <a data-deploy-link="api-docs" href="/docs">Docs</a>
  <a data-deploy-link="guide" href="/ai4ms-user-guide.html">Guide</a>
`;

test("injects repeatable guide version and commit metadata", () => {
  const source = `
    <meta name="ai4ms-guide-version" content="old" />
    <meta name="ai4ms-guide-commit" content="old" />
    <meta name="ai4ms-guide-channel" content="old" />
    <strong data-ai4ms-build-field="version">old</strong>
    <span data-ai4ms-build-field="commit">old</span>
    <span data-ai4ms-build-field="footer">old</span>
    ${links}
  `;
  const prepared = injectBuildMetadata(source, {
    version: "1.2.3",
    channel: "ai4ms",
    commit: "abc123",
  });
  assert.match(prepared, /content="1\.2\.3"/);
  assert.match(prepared, /v1\.2\.3 · ai4ms/);
  assert.match(prepared, /abc123/);
  assert.deepEqual(validateDeploymentLinks(prepared), []);
});

test("rejects a missing or unsafe deployment link", () => {
  const invalid = links
    .replace('data-deploy-link="guide" href="/ai4ms-user-guide.html"', 'data-deploy-link="guide" href="../guide"')
    .replace(/<a data-deploy-link="health"[^>]*>Health<\/a>/, "");
  const errors = validateDeploymentLinks(invalid);
  assert.ok(errors.some((item) => item.includes("missing deployment link: health")));
  assert.ok(errors.some((item) => item.includes("guide")));
});

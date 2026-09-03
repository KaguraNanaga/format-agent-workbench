import fs from "node:fs";

const debugPort = process.argv[2] || "9223";
const pageUrl = process.argv[3] || "http://127.0.0.1:8501/";
const screenshotPath = process.argv[4] || "streamlit-smoke.png";
const expectedText = process.argv[5] || "载入演示任务";
const runDemo = process.argv.includes("--demo");

const targetResponse = await fetch(
  `http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent(pageUrl)}`,
  { method: "PUT" },
);
if (!targetResponse.ok) {
  throw new Error(`Cannot create Chrome target: HTTP ${targetResponse.status}`);
}
const target = await targetResponse.json();
const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
let nextId = 1;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (!message.id || !pending.has(message.id)) return;
  const { resolve, reject } = pending.get(message.id);
  pending.delete(message.id);
  if (message.error) reject(new Error(message.error.message));
  else resolve(message.result);
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

function call(method, params = {}) {
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}

await call("Page.enable");
await call("Runtime.enable");
await call("Page.navigate", { url: pageUrl });

async function evaluate(expression) {
  const evaluation = await call("Runtime.evaluate", {
    expression,
    returnByValue: true,
  });
  return evaluation.result?.value;
}

async function waitForText(text, timeoutMs) {
  let bodyText = "";
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    bodyText = (await evaluate("document.body ? document.body.innerText : ''")) || "";
    if (bodyText.includes(text)) return bodyText;
  }
  throw new Error(
    `Expected text did not appear within ${timeoutMs / 1000} seconds: ${text}. ` +
      `Body: ${bodyText.slice(0, 500)}`,
  );
}

await waitForText(expectedText, 45000);
await waitForText("开始一次排版", 45000);

if (runDemo) {
  await new Promise((resolve) => setTimeout(resolve, 1000));
  const toggled = await evaluate(`(() => {
    const target =
      document.querySelector('input[aria-label="载入演示任务"]') ||
      document.querySelector('[role="switch"][aria-label="载入演示任务"]') ||
      [...document.querySelectorAll("label")].find(
        (item) => item.textContent.includes("载入演示任务"),
      );
    if (!target) return false;
    target.click();
    return true;
  })()`);
  if (!toggled) throw new Error("Cannot find the built-in demo toggle");
  await waitForText("示例格式要求已准备好", 30000);

  const started = await evaluate(`(() => {
    const buttons = [...document.querySelectorAll("button")];
    const target = buttons.find((item) => item.innerText.includes("开始排版"));
    if (!target || target.disabled) return false;
    target.click();
    return true;
  })()`);
  if (!started) throw new Error("Cannot find or enable the formatting button");
  await waitForText("下载排版后的 DOCX", 240000);
}

const capture = await call("Page.captureScreenshot", {
  format: "png",
  captureBeyondViewport: false,
});
fs.writeFileSync(screenshotPath, Buffer.from(capture.data, "base64"));
socket.close();

console.log(`Rendered OK: ${expectedText}`);
if (runDemo) console.log("Built-in demo completed OK");
console.log(`Screenshot: ${screenshotPath}`);

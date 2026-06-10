import fs from "node:fs";
import path from "node:path";

import { AuthClient, AuthorizationError } from "./src";

function readRepoEnv(): string {
  let dir = __dirname;
  for (let i = 0; i < 8; i++) {
    const p = path.join(dir, ".env");
    if (fs.existsSync(p)) {
      return fs.readFileSync(p, "utf-8");
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      break;
    }
    dir = parent;
  }
  throw new Error("未找到仓库根目录下的 .env（已从 __dirname 向上查找）");
}

function clientSecretFromEnv(text: string): string {
  for (const line of text.split("\n")) {
    const s = line.trim();
    if (!s || s.startsWith("#")) continue;
    const i = s.indexOf("=");
    if (i < 0) continue;
    if (s.slice(0, i).trim() !== "CLIENT_SECRET") continue;
    return s.slice(i + 1).trim().replace(/^["']|["']$/g, "");
  }
  return "";
}

async function main() {
  const secret = clientSecretFromEnv(readRepoEnv());
  if (!secret) {
    console.error("缺少 CLIENT_SECRET");
    process.exit(1);
  }

  const clients = [
    new AuthClient({
      serverUrl: "http://localhost:8000",
      softwareName: "软件ts示例",
      softwareVersion: "0.0.1",
      clientSecret: secret,
      debug: true,
    }),
  ];

  console.log("（模拟）界面/初始化已继续，后台刷新授权…");

  const jobs = clients.map((client) => {
    const { soft, promise } = client.startBackgroundRefresh({
      onDone: (r) => {
        if (r.success && r.authorized) {
          console.log("后台刷新：仍授权");
        } else {
          console.error(`后台刷新：${r.message || "失败"}（可在此禁用功能）`);
        }
      },
    });
    if (soft) {
      console.log(`产品 ${client.softwareName}: 可先依据本地快照启动`);
    } else {
      console.log(`产品 ${client.softwareName}: 无有效本地快照，需等待本次检查结果`);
    }
    return { client, soft, promise };
  });

  for (const { soft, promise } of jobs) {
    const r = await promise;
    if (!soft && (!r.success || !r.authorized)) {
      console.error(`未授权: ${r.message}`);
      process.exit(1);
    }
    if (soft && (!r.success || !r.authorized)) {
      console.error(`警告：本地曾放行但刷新失败: ${r.message}`);
    }
  }

  console.log("✅ 全部产品授权有效（含后台刷新结果）");
  const info = await clients[0].getAuthorizationInfo();
  if (!clients[0].debug) {
    console.log(JSON.stringify(info, null, 2));
  }
}

main().catch((e) => {
  if (e instanceof AuthorizationError) {
    console.error(`❌ ${e.message}`);
    process.exit(1);
  }
  console.error(e);
  process.exit(1);
});

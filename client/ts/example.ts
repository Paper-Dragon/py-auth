import fs from "node:fs";
import path from "node:path";
import * as readline from "node:readline/promises";

import { AuthClient } from "./src";

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

function buildPayUrl(client: AuthClient, autoPay = true): string {
  let url = `${client.serverUrl}/pay?device_id=${encodeURIComponent(client.deviceId)}`;
  if (autoPay) {
    url += "&auto_pay=1";
  }
  return url;
}

async function guidePayment(client: AuthClient): Promise<void> {
  const planInfo = await client.getPlanInfo();
  if (planInfo.success) {
    const label = planInfo.plan || "未知套餐";
    if (planInfo.price) {
      console.log(`当前套餐：${label}，价格：¥${planInfo.price}`);
    } else {
      console.log(`当前套餐：${label}`);
    }
    if (planInfo.plan_detail) {
      console.log(`套餐详情：${planInfo.plan_detail}`);
    }
  }

  const payUrl = buildPayUrl(client);
  console.log("设备未授权，请在浏览器打开以下链接完成付款：");
  console.log(`  ${payUrl}`);

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  await rl.question("付款完成后按回车继续...");
  rl.close();

  if (await client.requireAuthorization({ raiseException: false, forceOnline: true })) {
    console.log("付款成功，已授权");
  } else {
    console.log("仍未授权，请确认订单状态后重试");
  }
}

async function main() {
  const debug = true;
  const clientSecret = clientSecretFromEnv(readRepoEnv());

  const client = new AuthClient({
    serverUrl: "http://localhost:8000",
    softwareName: "软件ts示例",
    softwareVersion: "0.0.1",
    clientSecret,
    debug,
  });

  if (await client.requireAuthorization({ raiseException: false, forceOnline: true })) {
    console.log("已授权，正常启动");
  } else {
    await guidePayment(client);
  }

  const info = await client.getAuthorizationInfo();
  if (!debug) {
    console.log(JSON.stringify(info, null, 2));
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

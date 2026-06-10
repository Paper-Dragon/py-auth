import fs from "node:fs";
import os from "node:os";
import type {
  AuthClientConfig,
  AuthResult,
  AuthorizationInfo,
  CacheInfo,
  DeviceInfo,
  PaymentContext,
  PlanInfo,
} from "./types";
import { AuthorizationError } from "./errors";
import { encryptData, decryptData } from "./crypto";
import { AuthCache } from "./cache";
import { buildDeviceId, collectDeviceInfo, fetchPublicIp, loadPersistedDeviceId } from "./device";
import { getJson, postJson } from "./http";
import { getClientStorageRoot } from "./storage";
import { bundlePath } from "./stateBundle";
import { baseSdk } from "./sdkMeta";

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const SECONDS_PER_DAY = 86400;
const DEFAULT_HEARTBEAT_TIMEOUT_MS = 3_000;
const DEFAULT_PLAN_INFO_TIMEOUT_MS = 10_000;
const DEFAULT_PAYMENT_CONTEXT_TIMEOUT_MS = 10_000;

function resolveTimeoutMs(value: number | undefined, fallback: number): number {
  return value && value > 0 ? value : fallback;
}

type HeartbeatRequest = {
  device_id: string;
  software_name: string;
  device_info: DeviceInfo;
};

type EncryptedEnvelope = {
  encrypted_data: string;
};

type HeartbeatResponseDecrypted = {
  authorized?: boolean;
  message?: string;
  plan?: string;
};

export class AuthClient {
  readonly serverUrl: string;
  readonly softwareName: string;
  readonly softwareVersion: string;
  readonly deviceId: string;
  private deviceInfo: DeviceInfo;
  private deviceInfoDeferred: boolean;
  private readonly clientSecret: string;
  readonly debug: boolean;
  private readonly cache: AuthCache;
  private readonly stateBundleExistedBeforeInit: boolean;
  private lastPlan: string | undefined;
  private refreshInFlight = false;
  private readonly heartbeatTimeoutMs: number;
  private readonly planInfoTimeoutMs: number;
  private readonly paymentContextTimeoutMs: number;

  constructor(config: AuthClientConfig) {
    if (!config.serverUrl) throw new Error("serverUrl不能为空");
    if (!config.softwareName) throw new Error("softwareName不能为空");

    const secret = config.clientSecret ?? process.env.CLIENT_SECRET ?? "";
    if (!secret) {
      throw new Error(
        "client_secret未配置！请在初始化时传入（发行包中硬编码），或开发时设置环境变量CLIENT_SECRET。",
      );
    }

    this.serverUrl = config.serverUrl.replace(/\/+$/, "");
    this.softwareName = config.softwareName;
    this.softwareVersion = config.softwareVersion ?? "0.0.0";
    this.clientSecret = secret;
    this.debug = !!config.debug;
    this.heartbeatTimeoutMs = resolveTimeoutMs(config.heartbeatTimeoutMs, DEFAULT_HEARTBEAT_TIMEOUT_MS);
    this.planInfoTimeoutMs = resolveTimeoutMs(config.planInfoTimeoutMs, DEFAULT_PLAN_INFO_TIMEOUT_MS);
    this.paymentContextTimeoutMs = resolveTimeoutMs(
      config.paymentContextTimeoutMs,
      DEFAULT_PAYMENT_CONTEXT_TIMEOUT_MS,
    );

    const cacheValidityDays = config.cacheValidityDays ?? 7;
    const checkIntervalDays = config.checkIntervalDays ?? 2;

    const storageBase = getClientStorageRoot();

    const stateBundleExistedBeforeInit = fs.existsSync(bundlePath(this.serverUrl, storageBase));
    const hasStableDeviceId =
      !!config.deviceId || !!loadPersistedDeviceId(this.serverUrl, this.softwareName, storageBase);

    this.deviceId = buildDeviceId(this.serverUrl, config.deviceId, this.softwareName, storageBase);

    if (config.deviceInfo) {
      this.deviceInfoDeferred = false;
      this.deviceInfo = {
        ...config.deviceInfo,
        software_version: this.softwareVersion,
        sdk: baseSdk(process.version),
      };
    } else if (hasStableDeviceId) {
      this.deviceInfoDeferred = true;
      this.deviceInfo = {
        software_version: this.softwareVersion,
        sdk: baseSdk(process.version),
      };
    } else {
      this.deviceInfoDeferred = false;
      this.deviceInfo = {
        ...collectDeviceInfo(),
        software_version: this.softwareVersion,
        sdk: baseSdk(process.version),
      };
    }

    this.cache = new AuthCache({
      storageRoot: storageBase,
      deviceId: this.deviceId,
      serverUrl: this.serverUrl,
      softwareName: this.softwareName,
      cacheValidityDays,
      checkIntervalDays,
    });

    if (this.deviceInfoDeferred) {
      const snap = this.cache.loadDeviceInfoSnapshot();
      if (snap && typeof snap === "object") {
        this.deviceInfo = {
          ...snap,
          software_version: this.softwareVersion,
          sdk: baseSdk(process.version),
        };
        this.deviceInfoDeferred = false;
      }
    }

    this.stateBundleExistedBeforeInit = stateBundleExistedBeforeInit;
  }

  private logDebug(msg: string): void {
    if (this.debug) {
      
      console.debug(`[ts][DEBUG] ${msg}`);
    }
  }

  private ensureFullDeviceInfo(): void {
    if (!this.deviceInfoDeferred) return;
    this.deviceInfo = {
      ...collectDeviceInfo(),
      software_version: this.softwareVersion,
      sdk: baseSdk(process.version),
    };
    this.deviceInfoDeferred = false;
  }

  private enqueueDeviceInfoRefresh(): void {
    if (this.refreshInFlight) return;
    this.refreshInFlight = true;
    void (async () => {
      try {
        let enriched = false;

        const wasDeferred = this.deviceInfoDeferred;
        this.ensureFullDeviceInfo();
        if (wasDeferred) enriched = true;

        const hasPublicIp =
          typeof this.deviceInfo.network?.public_ip === "string" &&
          this.deviceInfo.network.public_ip.trim() !== "";
        if (!hasPublicIp) {
          const pub = (await fetchPublicIp()).trim();
          if (pub) {
            this.deviceInfo = {
              ...this.deviceInfo,
              network: { ...(this.deviceInfo.network ?? {}), public_ip: pub },
            };
            enriched = true;
          }
        }

        if (enriched) {
          this.logDebug("后台补全完成，发送补全心跳...");
          const snap = this.cache.snapshotForAuthorizationCheck();
          const nextHb = snap.storedHeartbeatTimes + 1;
          const r = await this.checkOnline(nextHb);
          if (r.success) {
            this.persistOnlineResult(r, r.authorized ? nextHb : undefined);
          }
        }
      } catch (e: unknown) {
        this.logDebug(`后台补全 device_info 失败: ${String(e)}`);
      } finally {
        this.refreshInFlight = false;
      }
    })();
  }

  private formatRemainingTime(cachedAtSeconds: number): string {
    if (!cachedAtSeconds || cachedAtSeconds <= 0) return "未知";

    const now = Date.now() / 1000;
    const elapsed = now - cachedAtSeconds;
    const remaining = this.cache.cacheValiditySeconds - elapsed;
    if (remaining <= 0) return "已过期";

    const days = Math.floor(remaining / SECONDS_PER_DAY);
    const hours = Math.floor((remaining % SECONDS_PER_DAY) / SECONDS_PER_HOUR);
    const minutes = Math.floor((remaining % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);

    const parts: string[] = [];
    if (days > 0) parts.push(`${days}天`);
    if (hours > 0) parts.push(`${hours}小时`);
    if (minutes > 0 || parts.length === 0) parts.push(`${minutes}分钟`);
    return parts.join("");
  }

  private async postHeartbeatDeviceInfo(
    deviceInfoPayload: DeviceInfo,
    heartbeatTimes: number,
    timeoutMs: number,
  ): Promise<AuthResult> {
    const device_info: DeviceInfo = {
      ...deviceInfoPayload,
      sdk: {
        ...(deviceInfoPayload.sdk ?? baseSdk(process.version)),
        heartbeat_times: heartbeatTimes,
      },
    };
    const requestData: HeartbeatRequest = {
      device_id: this.deviceId,
      software_name: this.softwareName,
      device_info,
    };
    const encrypted = encryptData(JSON.stringify(requestData), this.clientSecret);
    const { status, json, text } = await postJson<EncryptedEnvelope>(
      `${this.serverUrl}/api/auth/heartbeat`,
      { encrypted_data: encrypted },
      timeoutMs,
    );
    if (status === 200) {
      const token = json?.encrypted_data ?? "";
      const decryptedText = token ? decryptData(token, this.clientSecret) : null;
      if (!decryptedText) {
        this.logDebug("在线订阅响应解密失败");
        return { authorized: false, message: "解密响应失败", success: false, from_cache: false };
      }
      const decrypted = JSON.parse(decryptedText) as HeartbeatResponseDecrypted;
      const plan = typeof decrypted.plan === "string" ? decrypted.plan.trim() : "";
      if (plan) {
        this.lastPlan = plan;
      }
      this.logDebug(`在线订阅成功，authorized=${!!decrypted.authorized}`);
      return {
        authorized: !!decrypted.authorized,
        message: decrypted.message ?? "",
        success: true,
        from_cache: false,
        ...(this.lastPlan ? { plan: this.lastPlan } : {}),
      };
    }
    const detail = (json as any)?.detail;
    const msg = status === 403 && typeof detail === "string" ? detail : `服务器错误: ${status}`;
    this.logDebug(`在线订阅失败，status=${status}, message=${msg}; raw=${text}`);
    return { authorized: false, message: msg, success: false, from_cache: false, is_auth_error: status === 403 };
  }

  private async checkOnline(heartbeatTimes: number): Promise<AuthResult> {
    try {
      this.enqueueDeviceInfoRefresh();
      this.logDebug("开始在线订阅请求...");

      const device_info: DeviceInfo = {
        ...this.deviceInfo,
        software_version: this.softwareVersion,
        system: {
          ...(this.deviceInfo.system ?? {}),
          hostname: this.deviceInfo.system?.hostname?.trim() || os.hostname(),
          os: this.deviceInfo.system?.os || process.platform,
        },
      };
      return await this.postHeartbeatDeviceInfo(device_info, heartbeatTimes, this.heartbeatTimeoutMs);
    } catch (e: any) {
      const msg = e?.name === "AbortError" ? "连接失败: timeout" : `连接失败: ${String(e?.message ?? e)}`;
      this.logDebug(`在线订阅请求异常: ${msg}`);
      return { authorized: false, message: msg, success: false, from_cache: false };
    }
  }

  private persistOnlineResult(result: AuthResult, heartbeatIfAuthorized: number | undefined): void {
    const snap = result.authorized
      ? (JSON.parse(JSON.stringify(this.deviceInfo)) as DeviceInfo)
      : undefined;
    this.cache.saveCache(
      result.authorized,
      result.message,
      result.authorized ? heartbeatIfAuthorized : undefined,
      snap,
    );
  }

  async checkAuthorization(_forceOnline = false): Promise<AuthResult> {
    if (this.debug) {
      const cf = this.cache.cacheFile;
      const fileNow = fs.existsSync(cf);
      const pre = this.stateBundleExistedBeforeInit;
      let desc = "不存在（持久化可能失败）";
      if (fileNow && pre) desc = "启动前已存在";
      else if (fileNow && !pre) desc = "启动前不存在，构造客户端时已新建（device_id 持久化）";
      else if (!fileNow && pre) desc = "启动前曾有，当前缺失（异常）";
      this.logDebug(`状态包: ${cf} | ${desc}`);
    }

    const snap = this.cache.snapshotForAuthorizationCheck();
    const cacheData = snap.cacheData;
    const cacheValid = this.cache.isCacheTTLValid(cacheData);

    if (cacheValid) {
      this.logDebug("本地缓存仍在有效期内（在线失败时可作后备）");
      this.logDebug("缓存有效，继续尝试在线订阅来更新订阅");
    } else {
      this.logDebug(cacheData ? "缓存存在但已过期，准备发起在线订阅请求" : "未找到缓存，准备发起在线订阅请求");
    }

    const nextHb = snap.storedHeartbeatTimes + 1;
    const onlineResult = await this.checkOnline(nextHb);

    if (onlineResult.success) {
      this.logDebug("在线订阅成功，更新缓存");
      this.persistOnlineResult(onlineResult, nextHb);
      return onlineResult;
    }

    if (cacheValid && cacheData && !onlineResult.is_auth_error) {
      const remaining = this.formatRemainingTime(cacheData.cachedAt);
      this.logDebug(`在线订阅失败，但缓存有效，使用缓存结果，订阅剩余时间: ${remaining}`);
      return {
        authorized: cacheData.authorized,
        message: cacheData.message,
        success: true,
        from_cache: true,
      };
    }

    return onlineResult;
  }

  async checkAuthorizationProgressive(forceOnline = false): Promise<AuthResult> {
    return this.checkAuthorization(forceOnline);
  }

  async requireAuthorization(
    options?: boolean | { forceOnline?: boolean; raiseException?: boolean },
  ): Promise<boolean> {
    const forceOnline = typeof options === "boolean" ? options : (options?.forceOnline ?? false);
    const raiseException = typeof options === "boolean" ? true : (options?.raiseException ?? true);
    const result = await this.checkAuthorization(forceOnline);

    if (!result.success || !result.authorized) {
      if (raiseException) {
        throw new AuthorizationError({
          message: result.message,
          result,
          deviceId: this.deviceId,
          serverUrl: this.serverUrl,
        });
      }
      return false;
    }

    return true;
  }

  submitCheckAuthorization(forceOnline = false): Promise<AuthResult> {
    return this.checkAuthorization(forceOnline);
  }

  submitCheckAuthorizationProgressive(forceOnline = false): Promise<AuthResult> {
    return this.checkAuthorizationProgressive(forceOnline);
  }

  submitRequireAuthorization(
    options?: boolean | { forceOnline?: boolean; raiseException?: boolean },
  ): Promise<boolean> {
    return this.requireAuthorization(options);
  }

  clearCache(): boolean {
    return this.cache.clearCache();
  }

  canSoftLaunch(): boolean {
    const c = this.cache.getCache();
    return !!(c?.authorized && this.cache.isCacheTTLValid(c));
  }

  startBackgroundRefresh(options?: {
    forceOnline?: boolean;
    onDone?: (result: AuthResult) => void;
  }): { soft: boolean; promise: Promise<AuthResult> } {
    const soft = this.canSoftLaunch();
    const fo = options?.forceOnline ?? false;
    const promise = this.checkAuthorizationProgressive(fo).then(
      (r) => {
        options?.onDone?.(r);
        return r;
      },
      (err: unknown) => {
        const failed: AuthResult = {
          authorized: false,
          success: false,
          from_cache: false,
          message: err instanceof Error ? err.message : String(err),
        };
        options?.onDone?.(failed);
        return failed;
      },
    );
    return { soft, promise };
  }

  async getPlanInfo(): Promise<PlanInfo> {
    const requestData: Record<string, string> = {};
    if (this.softwareName) {
      requestData.software_name = this.softwareName;
    }
    try {
      const { status, json } = await postJson<EncryptedEnvelope>(
        `${this.serverUrl}/api/auth/plan-info`,
        { encrypted_data: encryptData(JSON.stringify(requestData), this.clientSecret) },
        this.planInfoTimeoutMs,
      );
      if (status === 200) {
        const token = json?.encrypted_data ?? "";
        const decryptedText = token ? decryptData(token, this.clientSecret) : null;
        if (!decryptedText) {
          return { success: false, message: "解密响应失败" };
        }
        return { success: true, ...(JSON.parse(decryptedText) as Omit<PlanInfo, "success">) };
      }
      const detail = (json as { detail?: string } | null)?.detail;
      const msg = status === 403 && typeof detail === "string" ? detail : `服务器错误: ${status}`;
      return { success: false, message: msg };
    } catch (e: unknown) {
      const msg = e instanceof Error && e.name === "AbortError" ? "连接失败: timeout" : `连接失败: ${String(e)}`;
      return { success: false, message: msg };
    }
  }

  async getPaymentContext(): Promise<PaymentContext> {
    const url = `${this.serverUrl}/api/payment/device-context?device_id=${encodeURIComponent(this.deviceId)}`;
    try {
      const { status, json } = await getJson<Omit<PaymentContext, "success">>(url, this.paymentContextTimeoutMs);
      if (status === 200 && json) {
        return { success: true, ...json };
      }
      return { success: false, message: `服务器错误: ${status}` };
    } catch (e: unknown) {
      const msg = e instanceof Error && e.name === "AbortError" ? "连接失败: timeout" : `连接失败: ${String(e)}`;
      return { success: false, message: msg };
    }
  }

  async getAuthorizationInfo(): Promise<AuthorizationInfo> {
    const cache = this.cache.getCache();

    const info: AuthorizationInfo = cache
      ? {
          authorized: cache.authorized,
          success: true,
          from_cache: true,
          message: cache.message,
          device_id: this.deviceId,
          server_url: this.serverUrl,
          cache_remaining_time: this.formatRemainingTime(cache.cachedAt),
          cache_valid: this.cache.isCacheTTLValid(cache),
          cached_at: cache.cachedAt,
          cached_at_readable:
            cache.cachedAt > 0
              ? new Date(cache.cachedAt * 1000).toISOString().replace("T", " ").slice(0, 19)
              : undefined,
        }
      : {
          authorized: false,
          success: false,
          from_cache: false,
          message: "无本地授权缓存",
          device_id: this.deviceId,
          server_url: this.serverUrl,
          cache_remaining_time: "无缓存",
          cache_valid: false,
        };

    if (this.lastPlan) {
      info.plan = this.lastPlan;
    }

    if (this.debug) {
      try {
        this.logDebug(`授权信息摘要:\n${JSON.stringify(info, null, 2)}`);
      } catch {}
    }

    return info;
  }

  getCacheInfo(): CacheInfo | null {
    const cache = this.cache.getCache();
    if (!cache) {
      return null;
    }
    const now = Date.now() / 1000;
    return {
      authorized: cache.authorized,
      message: cache.message,
      cached_at: cache.cachedAt,
      last_success_at: cache.cachedAt,
      cache_age_days: (now - cache.cachedAt) / SECONDS_PER_DAY,
      cache_valid: this.cache.isCacheTTLValid(cache),
      needs_check: this.cache.needsCheck(),
      cache_file: this.cache.cacheFile,
    };
  }
}

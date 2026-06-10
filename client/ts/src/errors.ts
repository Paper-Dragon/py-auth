import type { AuthResult } from "./types";

export class AuthorizationError extends Error {
  readonly result?: AuthResult;
  readonly deviceId?: string;
  readonly serverUrl?: string;

  constructor(args: {
    message: string;
    result?: AuthResult;
    deviceId?: string;
    serverUrl?: string;
  }) {
    super(args.message);
    this.name = "AuthorizationError";
    this.result = args.result;
    this.deviceId = args.deviceId;
    this.serverUrl = args.serverUrl;
  }

  isNetworkError(): boolean {
    const keywords = ["连接失败", "连接", "network", "timeout", "connection"];
    const sources = [this.message, this.result?.message ?? ""];
    return sources.some((text) => {
      const lower = text.toLowerCase();
      return keywords.some((keyword) => lower.includes(keyword.toLowerCase()));
    });
  }

  isTimeout(): boolean {
    const sources = [this.message, this.result?.message ?? ""];
    return sources.some((text) => {
      const lower = text.toLowerCase();
      return (
        lower.includes("timeout") ||
        text.includes("超时") ||
        lower.includes("deadline exceeded") ||
        lower.includes("context deadline")
      );
    });
  }

  isUnauthorized(): boolean {
    if (this.result) {
      return !this.result.authorized && this.result.success;
    }
    return this.message.includes("未授权") || this.message.includes("禁用");
  }

  isValidationError(): boolean {
    if (this.result) {
      return !this.result.success;
    }
    return this.message.includes("无法验证授权") || this.message.includes("验证失败");
  }
}

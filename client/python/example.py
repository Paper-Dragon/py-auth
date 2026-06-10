import json
from pathlib import Path
from typing import Optional


from py_auth_client import AuthClient, AuthorizationError


def _client_secret() -> Optional[str]:
    text = (Path(__file__).resolve().parent.parent.parent / ".env").read_text(encoding="utf-8")
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        if key.strip() == "CLIENT_SECRET":
            return val.strip().strip('"').strip("'") or None
    return None


def _build_pay_url(client: AuthClient, *, auto_pay: bool = True) -> str:
    """拼出网页支付页地址：付款由浏览器完成，SDK 只负责给出链接。"""
    url = f"{client.server_url}/pay?device_id={client.device_id}"
    if auto_pay:
        url += "&auto_pay=1"
    return url


def _guide_payment(client: AuthClient) -> None:
    """未授权时引导用户去支付页，付款后强制在线复查授权。"""
    plan_info = client.get_plan_info()
    if plan_info.get("success"):
        label = plan_info.get("plan_label") or plan_info.get("plan") or "未知套餐"
        price = plan_info.get("price")
        if price:
            print(f"当前套餐：{label}，价格：¥{price}")
        else:
            print(f"当前套餐：{label}")

    pay_url = _build_pay_url(client)
    print("设备未授权，请在浏览器打开以下链接完成付款：")
    print(f"  {pay_url}")

    input("付款完成后按回车继续...")
    if client.require_authorization(raise_exception=False, force_online=True):
        print("付款成功，已授权")
    else:
        print("仍未授权，请确认订单状态后重试")


def main() -> None:
    client = AuthClient(
        server_url="http://localhost:8000",
        software_name="aaaa",
        software_version="0.0.1",
        # client_secret=_client_secret(),
        client_secret="sk_8860d2a2579928fed1f412e07501eb3e",
        debug=True,
    )

    # force_online=True 确保拿到最新授权状态，而非本地缓存
    if client.require_authorization(raise_exception=False, force_online=True):
        print("已授权，正常启动")
    else:
        _guide_payment(client)

    info = client.get_authorization_info()
    if not client.debug:
        print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

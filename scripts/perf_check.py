#!/usr/bin/env python3
"""用 headless Chrome + CDP 测 tableflow 看板的两个性能门槛（005 SC-008）。

- 首屏：导航开始到表格首行渲染完成
- 滚动：表格容器连续横向滚动 5 秒的 rAF 平均帧率

只依赖标准库（手写最小 WebSocket 客户端）。用法：
    python3 scripts/perf_check.py [url] [--rows 14]
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

CHROME = os.environ.get("CHROME_BIN", "/usr/bin/google-chrome")
DEFAULT_URL = "http://127.0.0.1:5173/"
PORT = 9333

INJECT = r"""
(() => {
  window.__tf = { navStart: performance.timeOrigin };
  const mark = () => {
    const rows = document.querySelectorAll('tbody tr');
    if (!window.__tf.firstRow && rows.length > 0) {
      window.__tf.firstRow = performance.now();
      window.__tf.rowCount = rows.length;
    }
  };
  const start = () => {
    if (!document.documentElement) { setTimeout(start, 0); return; }
    mark();
    new MutationObserver(mark).observe(document.documentElement, {
      childList: true, subtree: true,
    });
  };
  start();
})();
"""

SCROLL = r"""
(() => new Promise((resolve) => {
  const wrap = document.querySelector('.table-wrap');
  if (!wrap) { resolve({ error: 'no .table-wrap' }); return; }
  const max = wrap.scrollWidth - wrap.clientWidth;
  if (max <= 0) { resolve({ error: 'no horizontal overflow', max }); return; }
  let frames = 0;
  let longTasks = 0;
  const t0 = performance.now();
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) if (e.duration > 50) longTasks += 1;
    }).observe({ type: 'longtask', buffered: false });
  } catch (e) { /* 不支持 longtask 就跳过 */ }
  const tick = () => {
    frames += 1;
    const t = performance.now() - t0;
    wrap.scrollLeft = max * (0.5 - 0.5 * Math.cos(t / 250));
    if (t < 5000) requestAnimationFrame(tick);
    else resolve({
      frames,
      seconds: (performance.now() - t0) / 1000,
      longTasks,
      max,
    });
  };
  requestAnimationFrame(tick);
}))()
"""


class WS:
    """够用的最小 WebSocket 客户端：只发文本帧、只收完整文本消息。"""

    def __init__(self, url: str) -> None:
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=20)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {u.path} HTTP/1.1\r\n"
            f"Host: {u.hostname}:{u.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        self.buf = buf.split(b"\r\n\r\n", 1)[1]

    def send(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        header = bytearray([0x81])
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def _read_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("websocket closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> dict:
        payload = b""
        while True:
            b1, b2 = self._read_exact(2)
            fin = b1 & 0x80
            opcode = b1 & 0x0F
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            masked = b2 & 0x80
            mask = self._read_exact(4) if masked else b""
            data = self._read_exact(length)
            if masked:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x8:
                raise ConnectionError("websocket close frame")
            if opcode == 0x9:  # ping
                continue
            payload += data
            if fin:
                return json.loads(payload.decode())

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def wait_for_target(timeout: float = 20.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list", timeout=2) as resp:
                targets = json.load(resp)
            for target in targets:
                if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                    return target["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(0.3)
    raise RuntimeError("Chrome 调试端口未就绪")


def main() -> int:
    url = DEFAULT_URL
    rows_expect = 0
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--rows" and i + 1 < len(args):
            rows_expect = int(args[i + 1])
            i += 2
            continue
        if not arg.startswith("--"):
            url = arg
        i += 1

    chrome = subprocess.Popen(
        [
            CHROME,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--window-size=1280,800",
            f"--remote-debugging-port={PORT}",
            "--user-data-dir=.tmp-shots/chrome-profile",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ws = WS(wait_for_target())
        seq = 0

        def call(method: str, params: dict | None = None) -> dict:
            nonlocal seq
            seq += 1
            ws.send({"id": seq, "method": method, "params": params or {}})
            while True:
                msg = ws.recv()
                if msg.get("id") == seq:
                    return msg

        call("Page.enable")
        call("Runtime.enable")
        call("Page.addScriptToEvaluateOnNewDocument", {"source": INJECT})
        call("Page.navigate", {"url": url})
        time.sleep(3.0)  # 等 React 拉数据并渲染

        first = call(
            "Runtime.evaluate",
            {
                "expression": "JSON.stringify(window.__tf || {})",
                "returnByValue": True,
            },
        )
        stats = json.loads(first["result"]["result"]["value"])
        first_row_ms = stats.get("firstRow")
        row_count = stats.get("rowCount")

        print(f"URL: {url}")
        if first_row_ms is None:
            print("首屏：未捕获到表格行（页面可能未加载出数据）")
        else:
            print(f"首屏：表格首行渲染完成 {first_row_ms:.0f}ms，行数 {row_count}")
            if rows_expect and row_count and row_count < rows_expect:
                print(f"  注意：行数少于期望的 {rows_expect} 行，首屏数字只作参考")

        scroll = call(
            "Runtime.evaluate",
            {
                "expression": SCROLL,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": 15000,
            },
        )
        result = scroll["result"].get("result", {})
        if result.get("subtype") == "error" or "exceptionDetails" in scroll["result"]:
            print("滚动：测量失败", scroll["result"].get("exceptionDetails"))
        else:
            value = result.get("value") or {}
            if "error" in value:
                print(f"滚动：跳过（{value['error']}）")
            else:
                fps = value["frames"] / value["seconds"]
                print(
                    f"滚动：{value['frames']} 帧 / {value['seconds']:.1f}s = {fps:.1f}fps，"
                    f">50ms 长任务 {value['longTasks']} 个"
                )
        ws.close()
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Máy chủ Gemini giả lập (chỉ dùng trong kiểm thử): trả lời generateContent theo định dạng REST của Gemini,
gọi công cụ (functionCall) khi được cấp tools, trả JSON khi được yêu cầu response_mime_type = application/json."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CALLS: list[dict] = []


def _resp(parts):
    return {"candidates": [{"content": {"role": "model", "parts": parts}, "finishReason": "STOP", "index": 0}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10, "totalTokenCount": 20}}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        key = self.headers.get("x-goog-api-key", "")
        CALLS.append({"path": self.path, "key": key, "body": body})
        if key == "BAD":
            return self._send(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}})
        if "missing-model" in self.path:
            return self._send(404, {"error": {"code": 404, "message": "model not found", "status": "NOT_FOUND"}})
        if ":generateContent" not in self.path:
            return self._send(404, {"error": {"code": 404, "message": "not found", "status": "NOT_FOUND"}})
        contents = body.get("contents", [])
        last = contents[-1] if contents else {"parts": []}
        text = " ".join(p.get("text", "") for p in last.get("parts", [])).lower()
        gc = body.get("generationConfig", {})
        if gc.get("responseMimeType") == "application/json":
            ids = [int(x) for x in re.findall(r"^\[(\d+)\]", text, flags=re.M)]
            out = {"nguyen_nhan": [{"ten": "Hàng cũ, hết hạn", "mo_ta": "Nhiều khách nhận hàng cũ", "muc_do": "cao", "id_bang_chung": ids[:2]},
                                   {"ten": "Nguyên nhân bịa", "mo_ta": "Không có bằng chứng", "muc_do": "thấp", "id_bang_chung": [987654321]}],
                   "giai_phap": [{"nguyen_nhan": 1, "hanh_dong": "Kiểm tra hạn dùng khi nhập kho", "uu_tien": "cao", "chi_so_theo_doi": "Tỷ lệ 1–2 sao"},
                                 {"nguyen_nhan": 2, "hanh_dong": "x", "uu_tien": "thấp", "chi_so_theo_doi": "y"}]}
            return self._send(200, _resp([{"text": json.dumps(out, ensure_ascii=False)}]))
        fr = [p["functionResponse"] for p in last.get("parts", []) if "functionResponse" in p]
        if fr:
            return self._send(200, _resp([{"text": "Theo dữ liệu hệ thống (" + fr[0]["name"] + "): " + json.dumps(fr[0]["response"], ensure_ascii=False)[:300]}]))
        if body.get("tools") and "thời tiết" not in text:
            name, args = ("list_risk_products", {"level": "high", "limit": 3}) if "rủi ro" in text else ("get_overview", {})
            return self._send(200, _resp([{"functionCall": {"name": name, "args": args}}]))
        return self._send(200, _resp([{"text": "Đây là câu trả lời kiến thức chung từ Gemini giả lập."}]))


def start() -> str:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}"

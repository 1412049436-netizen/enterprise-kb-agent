"""报错日志导入模块"""
import json
import csv
import hashlib
import uuid
from pathlib import Path
from loguru import logger


class ErrorLogImporter:
    """从 CSV / JSON / 纯文本 导入报错记录到向量库"""

    def from_json(self, path: str | Path) -> list[dict]:
        """导入 JSON 格式报错记录"""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        return self._process_records(data, str(path))

    def from_csv(self, path: str | Path) -> list[dict]:
        """导入 CSV 格式报错记录"""
        records = []
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                records.append(row)
        return self._process_records(records, str(path))

    def from_text(self, path: str | Path) -> list[dict]:
        """从纯文本日志提取报错信息（正则匹配）"""
        import re
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        # 匹配常见的错误模式
        patterns = [
            r"(Error|Exception|错误|报错|异常|失败|FATAL)[:\s]*(.+)",
            r"\[(ERROR|WARN)\]\s*(.+)",
        ]
        chunks = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            for pat in patterns:
                m = re.search(pat, line, re.IGNORECASE)
                if m:
                    err_msg = m.group(2) if m.lastindex >= 2 else line
                    chunks.append(self._make_record({
                        "error_message": err_msg,
                        "raw_log": line,
                    }, str(path)))
                    break
        logger.info(f"  文本解析: {path} → {len(chunks)} 条报错")
        return chunks

    def _process_records(self, records: list[dict], source: str) -> list[dict]:
        """将原始记录转为可索引的 chunk"""
        chunks = []
        for r in records:
            chunk = self._make_record(r, source)
            chunks.append(chunk)
        logger.info(f"  导入完成: {source} → {len(chunks)} 条")
        return chunks

    def _make_record(self, record: dict, source: str) -> dict:
        """构建报错 chunk"""
        # 构建搜索文本：错误码 + 错误信息 + 症状 + 方案
        parts = []
        for key in [
            "error_code", "error_message", "error_type",
            "symptoms", "root_cause", "solution",
        ]:
            if val := record.get(key):
                parts.append(f"{key}: {val}")

        content = "\n".join(parts)

        record_id = hashlib.md5(content.encode()).hexdigest()[:16]
        return {
            "content": content,
            "metadata": {
                "source": source,
                "type": "error_log",
                "error_code": record.get("error_code", ""),
                "error_type": record.get("error_type", ""),
                "severity": record.get("severity", "unknown"),
                "system": record.get("system", ""),
                "record_id": record_id,
            },
        }

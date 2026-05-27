"""文档解析模块 — 支持 PDF / Word / Markdown / TXT"""
import re
import uuid
import hashlib
from pathlib import Path
from loguru import logger

from ..config import CHUNK_SIZE, CHUNK_OVERLAP, MD_HEADER_LEVEL


class DocumentParser:
    """统一文档解析器，按文档类型选择解析策略"""

    SUPPORTED = {".pdf", ".docx", ".md", ".txt", ".markdown"}

    def parse(self, file_path: str | Path) -> list[dict]:
        """解析单文件 → 返回 chunk 列表 [{content, metadata}]"""
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        if ext not in self.SUPPORTED:
            raise ValueError(f"不支持的文件类型: {ext}")

        title = file_path.stem

        if ext == ".pdf":
            text = self._parse_pdf(file_path)
            chunks = self._chunk_text(text, title, str(file_path))
        elif ext == ".docx":
            text = self._parse_docx(file_path)
            chunks = self._chunk_text(text, title, str(file_path))
        elif ext in (".md", ".markdown"):
            chunks = self._parse_markdown(file_path)
        else:  # .txt
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            chunks = self._chunk_text(text, title, str(file_path))

        logger.info(f"  解析完成: {file_path.name} → {len(chunks)} chunks")
        return chunks

    def parse_directory(self, dir_path: str | Path) -> list[dict]:
        """批量解析目录下所有支持的文件"""
        dir_path = Path(dir_path)
        all_chunks = []
        files = sorted(
            f for f in dir_path.rglob("*") if f.suffix.lower() in self.SUPPORTED
        )
        logger.info(f"发现 {len(files)} 个文档待解析")
        for f in files:
            try:
                chunks = self.parse(f)
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(f"  解析失败: {f.name} — {e}")
        return all_chunks

    # ── 各格式解析器 ─────────────────────────────────

    def _parse_pdf(self, path: Path) -> str:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages.append(f"[第{i+1}页]\n{text}")
        return "\n\n".join(pages)

    def _parse_docx(self, path: Path) -> str:
        from docx import Document
        doc = Document(str(path))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    def _parse_markdown(self, path: Path) -> list[dict]:
        """Markdown 按标题层级分块，保留路径信息"""
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.split("\n")
        chunks = []
        current_headers = {}  # level → text
        current_lines = []
        current_start = 1

        for i, line in enumerate(lines + ["### ##END##"]):
            # 检测标题
            m = re.match(r"^(#{1,6})\s+(.+)", line)
            if m or i == len(lines):
                # 处理累积的内容
                content = "\n".join(current_lines).strip()
                if len(content) > 20:
                    # 构建 section 路径
                    section_parts = []
                    for lv in sorted(current_headers):
                        section_parts.append(current_headers[lv])
                    section = " > ".join(
                        section_parts[:MD_HEADER_LEVEL]
                    )

                    # 进一步递归切分过大 chunk
                    sub = self._chunk_text(
                        content,
                        title=path.stem,
                        source=str(path),
                        section=section,
                    )
                    chunks.extend(sub)

                current_lines = []
                if m:
                    level = len(m.group(1))
                    header_text = m.group(2).strip()
                    current_headers[level] = header_text
                    # 清除更深层级的标题
                    for lv in list(current_headers):
                        if lv > level:
                            del current_headers[lv]
            else:
                current_lines.append(line)

        return chunks

    # ── 通用分块 ──────────────────────────────────────

    def _chunk_text(
        self,
        text: str,
        title: str,
        source: str,
        section: str = "",
    ) -> list[dict]:
        """递归分块：先按段落分，过长再按句子切"""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        chunks = []
        buffer = ""
        for p in paragraphs:
            if len(buffer) + len(p) < CHUNK_SIZE:
                buffer += ("\n\n" if buffer else "") + p
            else:
                if buffer:
                    chunks.append(self._make_chunk(buffer, title, source, section))
                # 如果单个段落过长，按句子进一步切
                if len(p) > CHUNK_SIZE * 2:
                    sub = self._chunk_long_paragraph(p, title, source, section)
                    chunks.extend(sub)
                    buffer = ""
                else:
                    buffer = p

        if buffer:
            chunks.append(self._make_chunk(buffer, title, source, section))

        # 重叠处理
        if CHUNK_OVERLAP > 0 and len(chunks) > 1:
            for i in range(len(chunks) - 1):
                overlap_text = chunks[i + 1]["content"][:CHUNK_OVERLAP]
                if overlap_text not in chunks[i]["content"]:
                    chunks[i]["content"] += "\n" + overlap_text

        return chunks

    def _chunk_long_paragraph(
        self, text: str, title: str, source: str, section: str
    ) -> list[dict]:
        """长段落按句子切分"""
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        chunks = []
        buffer = ""
        for s in sentences:
            if len(buffer) + len(s) < CHUNK_SIZE:
                buffer += s
            else:
                if buffer:
                    chunks.append(self._make_chunk(buffer, title, source, section))
                buffer = s
        if buffer:
            chunks.append(self._make_chunk(buffer, title, source, section))
        return chunks

    def _make_chunk(
        self, content: str, title: str, source: str, section: str
    ) -> dict:
        """构建 chunk 数据结构"""
        chunk_id = hashlib.md5(content.encode()).hexdigest()[:16]
        return {
            "content": content,
            "metadata": {
                "source": source,
                "title": title,
                "section": section,
                "chunk_id": chunk_id,
            },
        }

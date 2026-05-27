"""documents 模块单元测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import tempfile
from backend.ingestion.documents import DocumentParser


class TestDocumentParser:

    def setup_method(self):
        self.parser = DocumentParser()

    def test_parse_txt_file(self):
        content = "这是第一段内容。\n\n这是第二段内容，用于测试分块功能。"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp = f.name

        try:
            chunks = self.parser.parse(tmp)
            assert len(chunks) >= 1
            assert all("content" in c for c in chunks)
            assert all("metadata" in c for c in chunks)
            assert all("chunk_id" in c["metadata"] for c in chunks)
        finally:
            Path(tmp).unlink()

    def test_chunk_has_required_metadata(self):
        content = "测试文档。" * 500
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp = f.name

        try:
            chunks = self.parser.parse(tmp)
            for chunk in chunks:
                meta = chunk["metadata"]
                assert "source" in meta
                assert "title" in meta
                assert "chunk_id" in meta
                assert len(meta["chunk_id"]) == 16
        finally:
            Path(tmp).unlink()

    def test_parse_markdown_with_headers(self):
        md_content = """# 第一章
这是第一章的内容，介绍系统的基本概念和设计理念，包含足够的文字以通过分块器的最小长度检查。

## 1.1 系统组件
系统由前端和后端组成。前端负责用户交互，后端负责数据处理和模型推理，两者通过REST API通信。
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(md_content)
            tmp = f.name

        try:
            chunks = self.parser.parse(tmp)
            assert len(chunks) >= 1
            sections = [
                c["metadata"].get("section", "")
                for c in chunks
                if c["metadata"].get("section")
            ]
            assert len(sections) >= 1
        finally:
            Path(tmp).unlink()

    def test_rejects_unsupported_extension(self):
        with pytest.raises(ValueError, match="不支持的文件类型"):
            self.parser.parse("test.xyz")

    def test_parse_directory_finds_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "doc1.txt").write_text("内容1", encoding="utf-8")
            (Path(tmpdir) / "doc2.txt").write_text("内容2", encoding="utf-8")
            (Path(tmpdir) / "ignore.jpg").write_text("图片")

            chunks = self.parser.parse_directory(tmpdir)
            assert len(chunks) >= 2

from __future__ import annotations

import logging
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError:
    raise ImportError("python-docx is required: pip install python-docx")

from src.application.ports.rag_ports import IDocxParser

logger = logging.getLogger(__name__)

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class DocxParser(IDocxParser):

    def parse(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() != ".docx":
            raise ValueError(f"Expected .docx file, got: {path.suffix}")

        try:
            doc = Document(str(path))
        except Exception as exc:
            raise ValueError(f"Cannot open .docx: {file_path}") from exc

        parts: list[str] = []

        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                text = "".join(
                    node.text or ""
                    for node in element.iter(f"{{{_W}}}t")  # уніфіковано
                ).strip()
                if text:
                    parts.append(text)
                # порожній параграф — явний роздільник між секціями
                else:
                    if parts and parts[-1] != "":
                        parts.append("")

            elif tag == "tbl":
                table_rows: list[str] = []
                for row in element.iter(f"{{{_W}}}tr"):
                    cells: list[str] = []
                    for cell in row.iter(f"{{{_W}}}tc"):
                        cell_text = "".join(
                            node.text or ""
                            for node in cell.iter(f"{{{_W}}}t")  # уніфіковано
                        ).strip()
                        if cell_text:
                            cells.append(cell_text)
                    if cells:
                        table_rows.append(" | ".join(cells))

                if table_rows:
                    parts.append("\n".join(table_rows))

        # Прибираємо trailing порожні маркери і з'єднуємо
        while parts and parts[-1] == "":
            parts.pop()

        result = "\n\n".join(parts)
        logger.debug(
            "[docx_parser] parsed %d chars, %d blocks from %s",
            len(result), len(parts), file_path,
        )
        return result
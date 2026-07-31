"""ADAPTER driven (offline) - blob store em disco local. Default do backend=mock."""

from __future__ import annotations

from pathlib import Path

from leia.config import get_settings


class FilesystemBlobStore:
    """Guarda os objetos sob `blob_dir/<key>` no disco (sem AWS)."""

    def __init__(self) -> None:
        self._root = Path(get_settings().blob_dir)

    def _path(self, key: str) -> Path:
        return self._root / key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def url(self, key: str) -> str:
        """Caminho local como file:// URI (baixável direto no navegador/dev)."""
        return self._path(key).resolve().as_uri()

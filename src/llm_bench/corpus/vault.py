"""Obsidian vault parsing: frontmatter, tags, wikilinks, and the note graph."""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
_INLINE_TAG_RE = re.compile(r"(?<!\S)#([A-Za-z][\w/-]*)")


@dataclass(frozen=True)
class ParsedNote:
    tags: set[str]
    body: str
    link_targets: tuple[str, ...]


def parse_note_text(text: str) -> ParsedNote:
    """Extract frontmatter tags, inline #tags, and [[wikilink]] targets."""
    tags: set[str] = set()
    body = text
    if match := _FRONTMATTER_RE.match(text):
        body = text[match.end() :]
        meta = yaml.safe_load(match.group(1)) or {}
        raw_tags = meta.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        tags.update(str(t) for t in raw_tags)
    tags.update(_INLINE_TAG_RE.findall(body))
    link_targets = tuple(t.strip() for t in _WIKILINK_RE.findall(body))
    return ParsedNote(tags=tags, body=body, link_targets=link_targets)


@dataclass(frozen=True)
class VaultNote:
    note_id: str  # posix path relative to corpus root, e.g. "vault/Concepts/Gizmo.md"
    title: str  # filename stem; wikilinks resolve against this
    folder: str  # first folder under vault/, "" for vault root
    tags: frozenset[str]
    body: str
    link_targets: tuple[str, ...] = field(default=())  # raw wikilink titles


class Vault:
    def __init__(self, notes: list[VaultNote]) -> None:
        self._notes = sorted(notes, key=lambda n: n.note_id)
        self._by_id = {n.note_id: n for n in self._notes}
        by_title = {n.title: n.note_id for n in self._notes}
        self._outlinks: dict[str, list[str]] = {n.note_id: [] for n in self._notes}
        self._backlinks: dict[str, list[str]] = {n.note_id: [] for n in self._notes}
        self.unresolved_links: set[tuple[str, str]] = set()
        for note in self._notes:
            for target in note.link_targets:
                target_id = by_title.get(target)
                if target_id is None:
                    self.unresolved_links.add((note.note_id, target))
                elif target_id not in self._outlinks[note.note_id]:
                    self._outlinks[note.note_id].append(target_id)
                    self._backlinks[target_id].append(note.note_id)

    @classmethod
    def load(cls, corpus_root: Path) -> "Vault":
        vault_dir = corpus_root / "vault"
        notes = []
        for path in sorted(vault_dir.rglob("*.md")) if vault_dir.exists() else []:
            parsed = parse_note_text(path.read_text(encoding="utf-8"))
            rel = path.relative_to(corpus_root)
            folder_parts = rel.parts[1:-1]  # strip "vault" prefix and filename
            notes.append(
                VaultNote(
                    note_id=rel.as_posix(),
                    title=path.stem,
                    folder="/".join(folder_parts),
                    tags=frozenset(parsed.tags),
                    body=parsed.body,
                    link_targets=parsed.link_targets,
                )
            )
        return cls(notes)

    def get(self, note_id: str) -> VaultNote:
        return self._by_id[note_id]

    def outlinks(self, note_id: str) -> list[str]:
        return list(self._outlinks[note_id])

    def backlinks(self, note_id: str) -> list[str]:
        return list(self._backlinks[note_id])

    def __iter__(self) -> Iterator[VaultNote]:
        return iter(self._notes)

    def __len__(self) -> int:
        return len(self._notes)

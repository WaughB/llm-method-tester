"""Tests for the Obsidian vault parser and note graph."""

from pathlib import Path

import pytest

from llm_bench.corpus.vault import Vault, parse_note_text


class TestParseNoteText:
    def test_frontmatter_tags_list_syntax(self) -> None:
        parsed = parse_note_text("---\ntags: [alpha, beta]\n---\nBody here.")
        assert parsed.tags == {"alpha", "beta"}
        assert parsed.body.strip() == "Body here."

    def test_inline_hashtags(self) -> None:
        parsed = parse_note_text("Something #tagged here, but not#this or a # alone.")
        assert parsed.tags == {"tagged"}

    def test_wikilinks_plain_and_aliased(self) -> None:
        parsed = parse_note_text("See [[Target Note]] and [[Other|the other one]].")
        assert parsed.link_targets == ("Target Note", "Other")

    def test_no_frontmatter_is_fine(self) -> None:
        parsed = parse_note_text("Just a body. #x")
        assert parsed.tags == {"x"}
        assert parsed.body.startswith("Just a body.")


class TestVault:
    @pytest.fixture
    def vault(self, mini_corpus_root: Path) -> Vault:
        return Vault.load(mini_corpus_root)

    def test_loads_all_notes(self, vault: Vault) -> None:
        assert len(vault) == 4

    def test_note_ids_are_posix_relative_paths(self, vault: Vault) -> None:
        ids = {n.note_id for n in vault}
        assert "vault/Concepts/Gizmo.md" in ids
        assert all("\\" not in i for i in ids)

    def test_note_metadata(self, vault: Vault) -> None:
        gizmo = vault.get("vault/Concepts/Gizmo.md")
        assert gizmo.title == "Gizmo"
        assert gizmo.folder == "Concepts"
        assert gizmo.tags == {"concept", "core"}

    def test_combined_frontmatter_and_inline_tags(self, vault: Vault) -> None:
        limits = vault.get("vault/Reference/Rate Limits.md")
        assert limits.tags == {"reference", "api"}

    def test_outlinks_resolved_to_note_ids(self, vault: Vault) -> None:
        gizmo = vault.get("vault/Concepts/Gizmo.md")
        assert set(vault.outlinks(gizmo.note_id)) == {
            "vault/Concepts/Widget Overview.md",
            "vault/Reference/Rate Limits.md",
        }

    def test_backlinks_computed(self, vault: Vault) -> None:
        assert set(vault.backlinks("vault/Concepts/Gizmo.md")) == {
            "vault/Concepts/Widget Overview.md",
            "vault/Reference/Rate Limits.md",
        }

    def test_unresolved_links_are_dropped_from_graph(self, vault: Vault) -> None:
        # Restart.md links to [[Missing Note]] which has no file
        assert vault.outlinks("vault/Runbooks/Restart.md") == ["vault/Concepts/Widget Overview.md"]

    def test_unresolved_links_are_reported(self, vault: Vault) -> None:
        assert vault.unresolved_links == {("vault/Runbooks/Restart.md", "Missing Note")}

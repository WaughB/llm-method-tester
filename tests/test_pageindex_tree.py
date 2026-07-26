"""Tests for the deterministic PageIndex heading-tree builder."""

from llm_bench.corpus.documents import Document
from llm_bench.strategies.pageindex import TreeNode, build_forest, subtree_text


def make_doc(text: str, doc_id: str = "docs/x.md") -> Document:
    return Document(doc_id=doc_id, title="X", text=text)


SAMPLE = """# Widget API

Intro paragraph.

## Endpoints

The /gizmo endpoint.

### Authentication

Use the X-Widget-Key header.

## Errors

RFC 7807 problem details.
"""


class TestBuildForest:
    def test_builds_hierarchy_from_headings(self) -> None:
        [root] = build_forest([make_doc(SAMPLE)])
        assert root.title == "Widget API"
        assert "Intro paragraph." in root.text
        assert [c.title for c in root.children] == ["Endpoints", "Errors"]
        endpoints = root.children[0]
        assert "/gizmo" in endpoints.text
        assert [c.title for c in endpoints.children] == ["Authentication"]

    def test_node_ids_sequential_and_unique(self) -> None:
        forest = build_forest([make_doc(SAMPLE), make_doc("# Two\n\nbody", doc_id="docs/y.md")])
        ids: list[str] = []

        def collect(node: TreeNode) -> None:
            ids.append(node.node_id)
            for child in node.children:
                collect(child)

        for root in forest:
            collect(root)
        assert len(ids) == len(set(ids))
        assert ids == sorted(ids)  # sequential in traversal order

    def test_every_node_knows_its_doc(self) -> None:
        [root] = build_forest([make_doc(SAMPLE)])
        assert root.doc_id == "docs/x.md"
        assert all(c.doc_id == "docs/x.md" for c in root.children)

    def test_doc_without_headings_gets_single_root(self) -> None:
        [root] = build_forest([make_doc("just plain text, no headings")])
        assert root.children == []
        assert "just plain text" in root.text
        assert root.title == "X"  # falls back to document title

    def test_subtree_text_includes_descendants(self) -> None:
        [root] = build_forest([make_doc(SAMPLE)])
        text = subtree_text(root.children[0])  # Endpoints
        assert "/gizmo" in text
        assert "X-Widget-Key" in text
        assert "RFC 7807" not in text  # sibling section excluded

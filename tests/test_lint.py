from __future__ import annotations

import json

from hermes_memory_wiki.config import MemoryWikiConfig
from hermes_memory_wiki.lint import lint_vault
from hermes_memory_wiki.vector_index import SearchDocument, VectorIndex, build_search_documents
from hermes_memory_wiki.vault import METADATA_DIRECTORY, initialize_vault, read_queryable_pages


def _config(root):
    return MemoryWikiConfig(vault_path=root)


def _write(root, relative_path, content):
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _page(
    *,
    page_id="concept:example",
    title="Example",
    page_type="concept",
    updated_at="2026-05-01T00:00:00+00:00",
    confidence=None,
    source_ids=(),
    claims="",
    questions=(),
    contradictions=(),
):
    confidence_line = f"confidence: {confidence}\n" if confidence is not None else ""
    source_lines = ""
    if source_ids:
        source_lines = "sourceIds:\n" + "".join(f"  - {source_id}\n" for source_id in source_ids)
    question_lines = ""
    if questions:
        question_lines = "questions:\n" + "".join(f"  - {question}\n" for question in questions)
    contradiction_lines = ""
    if contradictions:
        contradiction_lines = "contradictions:\n" + "".join(f"  - {item}\n" for item in contradictions)
    claims_block = f"claims:\n{claims}" if claims else ""
    return f"""---
id: {page_id}
title: {title}
pageType: {page_type}
updatedAt: {updated_at}
{confidence_line}{source_lines}{question_lines}{contradiction_lines}{claims_block}---
# {title}

Body for {title}.
"""


def _issue_codes(result):
    return [issue.code for issue in result.issues]


def _issues_by_code(result, code):
    return [issue for issue in result.issues if issue.code == code]


def test_missing_id_creates_structure_error_without_silent_defaulting(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/no-id.md",
        """---
title: No ID
pageType: concept
updatedAt: 2026-05-01T00:00:00+00:00
---
# No ID
""",
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "missing-id")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].path == "concepts/no-id.md"


def test_missing_page_type_creates_structure_error(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/no-page-type.md",
        """---
id: concept:no-page-type
title: No Page Type
updatedAt: 2026-05-01T00:00:00+00:00
---
# No Page Type
""",
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "missing-page-type")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].path == "concepts/no-page-type.md"
    assert issues[0].details == {"expected": "concept"}


def test_missing_title_creates_structure_error_without_using_heading_or_path(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/no-title.md",
        """---
id: concept:no-title
pageType: concept
updatedAt: 2026-05-01T00:00:00+00:00
---
# Heading Is Not Frontmatter Title
""",
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "missing-title")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].path == "concepts/no-title.md"


def test_non_source_non_report_pages_missing_source_ids_create_provenance_warning(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "entities/ada.md", _page(page_id="entity:ada", title="Ada", page_type="entity"))
    _write(root, "concepts/engine.md", _page(page_id="concept:engine", title="Engine", page_type="concept"))
    _write(root, "syntheses/synthesis.md", _page(page_id="synthesis:one", title="Synthesis", page_type="synthesis"))
    _write(root, "sources/source.md", _page(page_id="source:one", title="Source", page_type="source"))
    _write(root, "reports/report.md", _page(page_id="report:one", title="Report", page_type="report"))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "missing-source-ids")
    assert sorted(str(issue.path) for issue in issues) == [
        "concepts/engine.md",
        "entities/ada.md",
        "syntheses/synthesis.md",
    ]
    assert {issue.severity for issue in issues} == {"warning"}
    assert {issue.category for issue in issues} == {"provenance"}


def test_stale_claim_updated_at_creates_quality_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/stale-claim.md",
        _page(
            source_ids=("source:one",),
            claims="  - id: claim:old\n    text: Old claim.\n    updatedAt: 2000-01-01T00:00:00+00:00\n    evidence:\n      - sourceId: source:one\n",
        ),
    )
    _write(root, "sources/source.md", _page(page_id="source:one", title="Source", page_type="source"))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "stale-claim")
    assert len(issues) == 1
    assert issues[0].severity == "issue"
    assert issues[0].category == "quality"
    assert issues[0].path == "concepts/stale-claim.md"
    assert issues[0].claim_id == "claim:old"


def test_broken_wikilink_creates_links_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/links.md",
        _page(source_ids=("source:one",)) + "\nSee [[concepts/missing.md]] and [[Missing Page]].\n",
    )
    _write(root, "sources/source.md", _page(page_id="source:one", title="Source", page_type="source"))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "broken-wikilink")
    assert [(issue.category, issue.details["target"]) for issue in issues] == [
        ("links", "Missing Page"),
        ("links", "concepts/missing.md"),
    ]


def test_source_provenance_fields_required_for_openclaw_source_types(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "sources/bridge.md",
        _page(page_id="source:bridge", title="Bridge", page_type="source")
        .replace("updatedAt:", "sourceType: memory-bridge\nupdatedAt:"),
    )
    _write(
        root,
        "sources/events.md",
        _page(page_id="source:events", title="Events", page_type="source")
        .replace("updatedAt:", "sourceType: memory-bridge-events\nbridgeRelativePath: memories/events.jsonl\nupdatedAt:"),
    )
    _write(
        root,
        "sources/unsafe.md",
        _page(page_id="source:unsafe", title="Unsafe", page_type="source")
        .replace("updatedAt:", "sourceType: unsafe-local\nunsafeLocalConfiguredPath: /tmp/memory\nupdatedAt:"),
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "missing-source-provenance")
    assert [(issue.path, issue.details["field"]) for issue in issues] == [
        ("sources/bridge.md", "bridgeRelativePath"),
        ("sources/bridge.md", "bridgeWorkspaceDir"),
        ("sources/events.md", "bridgeWorkspaceDir"),
        ("sources/unsafe.md", "unsafeLocalRelativePath"),
    ]
    assert {issue.severity for issue in issues} == {"warning"}
    assert {issue.category for issue in issues} == {"provenance"}


def test_missing_claim_evidence_creates_provenance_warning(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/evidence.md",
        _page(claims="  - id: claim:evidence-1\n    text: This claim has no evidence.\n"),
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "claim-missing-evidence")
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].category == "provenance"
    assert issues[0].path == "concepts/evidence.md"
    assert issues[0].claim_id == "claim:evidence-1"


def test_contradictions_create_contradiction_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/conflict.md", _page(contradictions=("A conflicts with B.",)))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "contradiction")
    assert len(issues) == 1
    assert issues[0].severity == "issue"
    assert issues[0].category == "contradictions"
    assert "A conflicts with B." in issues[0].message


def test_questions_create_open_question_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/question.md", _page(questions=("What remains unknown?",)))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "open-question")
    assert len(issues) == 1
    assert issues[0].category == "open-questions"
    assert "What remains unknown?" in issues[0].message


def test_low_confidence_creates_low_confidence_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/low.md",
        _page(
            confidence=0.4,
            claims="  - id: claim:low-1\n    text: Weak claim.\n    confidence: 0.2\n    evidence:\n      - path: sources/source.md\n",
        ),
    )
    _write(root, "sources/source.md", _page(page_id="source:source", title="Source", page_type="source"))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "low-confidence")
    assert [(issue.path, issue.claim_id) for issue in issues] == [
        ("concepts/low.md", None),
        ("concepts/low.md", "claim:low-1"),
    ]


def test_stale_updated_at_creates_stale_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/stale.md", _page(updated_at="2000-01-01T00:00:00+00:00"))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "stale-updated-at")
    assert len(issues) == 1
    assert issues[0].category == "quality"
    assert issues[0].path == "concepts/stale.md"


def test_duplicate_ids_create_schema_error(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/one.md", _page(page_id="concept:duplicate", title="One"))
    _write(root, "concepts/two.md", _page(page_id="concept:duplicate", title="Two"))

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "duplicate-id")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].details["id"] == "concept:duplicate"
    assert issues[0].details["paths"] == ["concepts/one.md", "concepts/two.md"]


def test_invalid_markdown_creates_schema_error(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/invalid.md",
        """---
id: [unterminated
title: Invalid
pageType: concept
updatedAt: 2026-05-01T00:00:00+00:00
---
# Invalid
""",
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "invalid-markdown")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].path == "concepts/invalid.md"


def test_page_type_must_match_directory_derived_broad_kind(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "entities/ada.md",
        _page(page_id="entity.ada", title="Ada", page_type="person"),
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "page-type-mismatch")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].path == "entities/ada.md"
    assert issues[0].details == {"expected": "entity", "actual": "person"}


def test_page_type_must_match_each_openclaw_queryable_directory(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    cases = [
        ("concepts/engine.md", "concept.engine", "Wrong Concept", "entity", "concept"),
        ("syntheses/foo.md", "synthesis.foo", "Wrong Synthesis", "entity", "synthesis"),
        ("sources/foo.md", "source.foo", "Wrong Source", "entity", "source"),
        ("reports/foo.md", "report.foo", "Wrong Report", "entity", "report"),
    ]
    for path, page_id, title, actual, _expected in cases:
        _write(root, path, _page(page_id=page_id, title=title, page_type=actual))

    result = lint_vault(_config(root))

    mismatches = sorted(
        (issue.path, issue.details["expected"], issue.details["actual"])
        for issue in _issues_by_code(result, "page-type-mismatch")
    )
    assert mismatches == [
        ("concepts/engine.md", "concept", "entity"),
        ("reports/foo.md", "report", "entity"),
        ("sources/foo.md", "source", "entity"),
        ("syntheses/foo.md", "synthesis", "entity"),
    ]


def test_duplicate_claim_ids_create_schema_error(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/one.md",
        _page(
            page_id="concept:one",
            title="One",
            claims="  - id: claim:duplicate\n    text: First claim.\n    evidence:\n      - text: observed\n",
        ),
    )
    _write(
        root,
        "concepts/two.md",
        _page(
            page_id="concept:two",
            title="Two",
            claims="  - id: claim:duplicate\n    text: Second claim.\n    evidence:\n      - text: observed\n",
        ),
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "duplicate-claim-id")
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].category == "structure"
    assert issues[0].claim_id == "claim:duplicate"
    assert issues[0].details["id"] == "claim:duplicate"
    assert issues[0].details["paths"] == ["concepts/one.md", "concepts/two.md"]


def test_broken_source_links_create_broken_link_issue(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(
        root,
        "concepts/broken.md",
        _page(
            source_ids=("source:missing",),
            claims="  - id: claim:broken-1\n    text: Broken evidence.\n    evidence:\n      - path: sources/missing.md\n      - sourceId: source:also-missing\n",
        ),
    )

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "broken-source-link")
    assert [(issue.path, issue.claim_id, issue.details["target"]) for issue in issues] == [
        ("concepts/broken.md", None, "source:missing"),
        ("concepts/broken.md", "claim:broken-1", "sources/missing.md"),
        ("concepts/broken.md", "claim:broken-1", "source:also-missing"),
    ]


def test_stale_vector_index_creates_vector_index_warning(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    page_path = _write(root, "concepts/vector.md", _page(title="Vector", claims="  - id: claim:vector-1\n    text: Original claim.\n    evidence:\n      - text: observed\n"))
    old_docs = build_search_documents(read_queryable_pages(root))
    index = VectorIndex(root / METADATA_DIRECTORY / "vector" / "index.sqlite")
    index.upsert_documents(old_docs)
    page_path.write_text(_page(title="Vector", claims="  - id: claim:vector-1\n    text: Changed claim.\n    evidence:\n      - text: observed\n"), encoding="utf-8")

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "stale-vector-index")
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].category == "vector-index"
    assert issues[0].path == "concepts/vector.md"


def test_missing_and_extra_vector_documents_create_vector_index_warnings(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/vector.md", _page(title="Vector"))
    extra_doc = SearchDocument(
        id="page:concepts/removed.md",
        page_path="concepts/removed.md",
        kind="concept",
        title="Removed",
        doc_type="page",
        text="Removed document",
        text_hash="removed-hash",
        metadata={},
    )
    index = VectorIndex(root / METADATA_DIRECTORY / "vector" / "index.sqlite")
    index.upsert_documents([extra_doc])

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "stale-vector-index")
    assert len(issues) == 2
    assert {issue.category for issue in issues} == {"vector-index"}
    assert {issue.severity for issue in issues} == {"warning"}
    assert {issue.path for issue in issues} == {"concepts/vector.md", None}
    assert {issue.details.get("documentId") for issue in issues} == {
        "page:concepts/vector.md",
        "page:concepts/removed.md",
    }


def test_symlinked_vector_directory_is_not_followed(tmp_path):
    root = tmp_path / "vault"
    outside = tmp_path / "outside-vector"
    initialize_vault(_config(root))
    _write(root, "concepts/vector.md", _page(title="Vector"))
    outside.mkdir()
    extra_doc = SearchDocument(
        id="page:outside.md",
        page_path="outside.md",
        kind="concept",
        title="Outside",
        doc_type="page",
        text="Outside document",
        text_hash="outside-hash",
        metadata={},
    )
    VectorIndex(outside / "index.sqlite").upsert_documents([extra_doc])
    vector_dir = root / METADATA_DIRECTORY / "vector"
    vector_dir.rmdir()
    vector_dir.symlink_to(outside, target_is_directory=True)

    result = lint_vault(_config(root))

    issues = _issues_by_code(result, "stale-vector-index")
    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].category == "vector-index"
    assert "symlink" in issues[0].message.lower()
    assert issues[0].details["indexPath"] == f"{METADATA_DIRECTORY}/vector"
    assert "documentId" not in issues[0].details


def test_lint_report_written_as_markdown_and_json(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/report.md", _page(questions=("Document this?",)))

    result = lint_vault(_config(root))

    assert result.markdown_path == root / METADATA_DIRECTORY / "cache" / "lint-report.md"
    assert result.json_path == root / METADATA_DIRECTORY / "cache" / "lint-report.json"
    assert result.markdown_path in result.updated_files
    assert result.json_path in result.updated_files
    markdown = result.markdown_path.read_text(encoding="utf-8")
    assert "# Memory Wiki Lint Report" in markdown
    assert "open-question" in markdown
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["summary"]["issueCount"] == len(result.issues)
    assert payload["issues"][0]["code"] == "open-question"


def test_second_lint_with_unchanged_reports_has_no_updated_files(tmp_path):
    root = tmp_path / "vault"
    initialize_vault(_config(root))
    _write(root, "concepts/report.md", _page(questions=("Document this?",)))

    first = lint_vault(_config(root))
    first_markdown = first.markdown_path.read_text(encoding="utf-8")
    first_json = first.json_path.read_text(encoding="utf-8")
    second = lint_vault(_config(root))

    assert second.updated_files == []
    assert second.markdown_path.read_text(encoding="utf-8") == first_markdown
    assert second.json_path.read_text(encoding="utf-8") == first_json

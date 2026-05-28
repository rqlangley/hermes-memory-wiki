import json

from hermes_memory_wiki import plugin


class FakeContext:
    def __init__(self):
        self.tools = {}
        self.skills = {}

    def register_tool(self, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_skill(self, name, path, **kwargs):
        self.skills[name] = {"path": path, **kwargs}


def _registered_tools():
    ctx = FakeContext()
    plugin.register(ctx)
    return ctx.tools


def _payload(result):
    assert isinstance(result, str)
    payload = json.loads(result)
    assert isinstance(payload["text"], str)
    assert payload["text"]
    assert isinstance(payload["details"], dict)
    return payload


def test_conversation_source_to_typed_upsert_compile_search_get_lint_workflow(tmp_path):
    vault = tmp_path / "vault"
    tools = _registered_tools()

    ingest = _payload(
        tools["wiki_ingest"]["handler"](
            {
                "vaultPath": str(vault),
                "sourceType": "conversation-summary",
                "title": "User Guidance Conversation",
                "body": "The user guidance says Project Atlas needs consent-first retrieval and source-backed claims.",
                "sessionId": "session-authoring-smoke",
                "messageRange": "1-3",
            }
        )
    )
    source_id = ingest["details"]["id"]
    assert source_id == "source.user-guidance-conversation"

    apply = _payload(
        tools["wiki_apply"]["handler"](
            {
                "vaultPath": str(vault),
                "op": "upsert_concept",
                "title": "Project Atlas Guidance",
                "body": "Project Atlas guidance emphasizes consent-first retrieval and source-backed claims.",
                "sourceIds": [source_id],
                "claims": [
                    {
                        "text": "Project Atlas should use consent-first retrieval.",
                        "evidence": [
                            {
                                "kind": "source",
                                "sourceId": source_id,
                                "path": ingest["details"]["path"],
                            }
                        ],
                    }
                ],
            }
        )
    )
    page_id = apply["details"]["id"]
    assert apply["details"]["path"] == "concepts/project-atlas-guidance.md"
    assert page_id == "concept.project-atlas-guidance"

    compile_payload = _payload(tools["wiki_compile"]["handler"]({"vaultPath": str(vault)}))
    assert compile_payload["details"]["pageCounts"]["source"] == 1
    assert compile_payload["details"]["pageCounts"]["concept"] == 1
    assert compile_payload["details"]["claimCount"] == 1

    search = _payload(
        tools["wiki_search"]["handler"](
            {"vaultPath": str(vault), "query": "consent-first retrieval", "searchMode": "keyword"}
        )
    )
    assert any(result["path"] == "concepts/project-atlas-guidance.md" for result in search["details"]["results"])

    get = _payload(tools["wiki_get"]["handler"]({"vaultPath": str(vault), "lookup": page_id}))
    assert get["details"]["found"] is True
    assert get["details"]["path"] == "concepts/project-atlas-guidance.md"
    assert get["details"]["sourceIds"] == [source_id]
    assert "consent-first retrieval" in get["details"]["content"]

    lint = _payload(tools["wiki_lint"]["handler"]({"vaultPath": str(vault)}))
    assert lint["details"]["errorCount"] == 0

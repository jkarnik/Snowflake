import pytest

from run_eval import EVALS, facts, load_prompt


def test_every_eval_prompt_loads_with_its_placeholders_filled():
    values = {"company_a": "Acme", "company_b": "Globex", "company_c": "Initech", "npm_account_id": 42}
    text = EVALS.read_text()
    prompts = {f"E{i}": load_prompt(f"E{i}", text, values) for i in range(1, 11)}
    assert prompts["E4"] == "Who are the AE and TSM for Acme?"
    assert prompts["E6"] == "How much data did account 42 ingest per day last week?"
    assert not any("{{" in p for p in prompts.values())


def test_a_missing_value_is_named():
    with pytest.raises(KeyError, match="company_a"):
        load_prompt("E4", EVALS.read_text(), {})


def test_facts_reads_a_stream_json_transcript():
    events = [
        {"type": "system", "subtype": "init"},
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": "snowflake"}},
            {"type": "tool_use", "name": "mcp__snowflake__status", "input": {}},
            {"type": "tool_use", "name": "mcp__snowflake__run_query", "input": {"sql": "SELECT 1"}},
        ]}},
        {"type": "result", "result": "Answer text", "permission_denials": []},
    ]
    assert facts(events) == {"skill_triggered": True, "status_calls": 1, "run_query_calls": 1,
                             "permission_denials": 0, "answer": "Answer text"}

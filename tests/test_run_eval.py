import pytest

from run_eval import EVALS, build_command, facts, load_prompt


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
                             "permission_denials": 0, "answer": "Answer text", "result_seen": True}


def test_facts_flags_a_transcript_without_a_result():
    assert facts([])["result_seen"] is False
    result = facts([])
    assert result["skill_triggered"] is False
    assert result["status_calls"] == 0
    assert result["run_query_calls"] == 0
    assert result["permission_denials"] == 0


def test_baseline_window_cannot_read_local_files_and_skill_window_is_unchanged():
    skill = build_command("Prompt text", "skill")
    baseline = build_command("Prompt text", "baseline")
    for flag in ("--disable-slash-commands", "--allowedTools", "--disallowedTools"):
        assert flag not in skill
        assert flag in baseline
    # the variadic flags come last, so neither can swallow the prompt or each other's values
    assert baseline[baseline.index("--allowedTools") + 1:baseline.index("--disallowedTools")] == [
        "mcp__snowflake__run_query", "mcp__snowflake__status"]
    assert baseline[baseline.index("--disallowedTools") + 1:] == ["Read", "Grep", "Glob", "Bash"]
    assert skill[2] == baseline[2] == "Prompt text"

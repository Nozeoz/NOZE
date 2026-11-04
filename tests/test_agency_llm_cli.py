"""The Claude Code CLI brain (``claude -p`` on a subscription): command line, stdin, parsing,
metering and failure modes — with a fake ``subprocess.run``, so no test ever calls Claude."""

import json
import subprocess
from pathlib import Path

import pytest

from noze.agency import llm as llm_mod
from noze.agency.config import AgencySettings
from noze.agency.llm import LLM, LLMError, image_block, text_block
from noze.agency.schemas import APPROVAL
from noze.agency.store import Store
from noze.config import Settings


def result_line(**kw):
    base = {"type": "result", "subtype": "success", "is_error": False, "result": "", "total_cost_usd": 0.0123,
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 900, "outputTokens": 150,
                                               "cacheReadInputTokens": 2000, "cacheCreationInputTokens": 0}}}
    base.update(kw)
    return json.dumps(base)


class FakeCLI:
    """Plays `claude auth status` and `claude -p`; records every call."""

    def __init__(self, answers, logged_in=True):
        self.answers = list(answers)  # stdout for each -p call, in order
        self.logged_in = logged_in
        self.calls = []

    def __call__(self, cmd, **kw):
        if cmd[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"loggedIn": self.logged_in}), "")
        sp = Path(cmd[cmd.index("--system-prompt-file") + 1])
        self.calls.append({"cmd": cmd, "stdin": kw.get("input"), "cwd": kw.get("cwd"),
                           "system": sp.read_text(encoding="utf-8"), "env": kw.get("env") or {}})
        out = self.answers.pop(0)
        return subprocess.CompletedProcess(cmd, 0, '{"type":"system","subtype":"init"}\n' + out + "\n", "")


@pytest.fixture
def make(tmp_path, monkeypatch):
    fake_bin = tmp_path / "claude.exe"
    fake_bin.write_bytes(b"")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm_mod, "_has_credentials", lambda: False)

    def build(fake, **env):
        monkeypatch.setattr(llm_mod.subprocess, "run", fake)
        e = {"NOZE_DATA_DIR": str(tmp_path), "AGENCY_LLM": "auto", "AGENCY_CLAUDE_BIN": str(fake_bin), **env}
        cfg = AgencySettings.load(Settings.load(env=e, dotenv=False), env=e, dotenv=False)
        store = Store(tmp_path / "a.db")
        return LLM(cfg, store), store

    return build


def test_no_api_key_uses_the_logged_in_cli(make, tmp_path, monkeypatch):
    answer = {"decision": "approve", "reasons": ["clean"]}
    fake = FakeCLI([result_line(structured_output=answer)])
    llm, store = make(fake)
    assert llm.available and llm.backend == "cli"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-stray")  # must not leak into the subscription CLI
    img = tmp_path / "f.jpg"
    img.write_bytes(b"\xff\xd8jpegbytes")
    out = llm.json("manager", "SOP " * 20000, [image_block(img), text_block("TASK")], APPROVAL, job_id=7)
    assert out["decision"] == "approve" and out["notes_for_editor"] == []  # conformed to the contract
    call = fake.calls[0]
    cmd = call["cmd"]
    assert cmd[cmd.index("--model") + 1] == "claude-opus-5-5" and cmd[cmd.index("--effort") + 1] == "medium"
    assert json.loads(cmd[cmd.index("--json-schema") + 1]) == APPROVAL
    for flag in ("--strict-mcp-config", "--disable-slash-commands", "--no-session-persistence"):
        assert flag in cmd  # the cheap flags: without them one call carries ~180k tokens of context
    assert cmd[cmd.index("--tools") + 1] == "" and cmd[cmd.index("--setting-sources") + 1] == "project"
    assert call["system"].startswith("SOP SOP") and len(" ".join(cmd)) < 32000  # big prompt goes via file
    msg = json.loads(call["stdin"])
    assert msg["type"] == "user" and msg["message"]["content"][0]["type"] == "image"
    assert msg["message"]["content"][1] == {"type": "text", "text": "TASK"}
    assert Path(call["cwd"]).name.startswith("noze-claude-") and not Path(call["cwd"]).exists()
    assert "ANTHROPIC_API_KEY" not in call["env"]
    assert store.spend(job_ids=[7]) == pytest.approx(0.0123)


def test_role_models_follow_the_model_map(make):
    fake = FakeCLI([result_line(structured_output={"decision": "approve"})] * 2)
    llm, _ = make(fake)
    llm.json("analyst", "S", "T", APPROVAL)
    llm.json("reviewer", "S", "T", APPROVAL)
    models = [c["cmd"][c["cmd"].index("--model") + 1] for c in fake.calls]
    assert models == ["claude-sonnet-5-5", "claude-opus-5-5"]
    llm2, _ = make(FakeCLI([result_line(structured_output={})]), AGENCY_MODEL_ANALYST="claude-haiku-5-5")
    assert llm2.cfg.model_for("analyst") == "claude-haiku-5-5"


def test_text_answer_in_a_fence_is_parsed_and_bad_json_is_retried(make):
    fake = FakeCLI([result_line(result="not json at all"),
                    result_line(result='Here:\n```json\n{"decision": "reject", "reasons": ["meh"]}\n```')])
    llm, _ = make(fake)
    out = llm.json("manager", "S", "T", APPROVAL)
    assert out["decision"] == "reject" and len(fake.calls) == 2


def test_two_bad_answers_raise_so_the_role_falls_back(make):
    llm, _ = make(FakeCLI([result_line(result="nope"), result_line(result="still nope")]))
    with pytest.raises(LLMError, match="no usable answer"):
        llm.json("manager", "S", "T", APPROVAL)


def test_logged_out_cli_is_unavailable_with_the_fix(make):
    llm, _ = make(FakeCLI([], logged_in=False))
    assert not llm.available and "claude auth login" in llm.reason


@pytest.mark.parametrize("msg", ["Failed to authenticate: OAuth session expired",
                                 "Invalid API key · Please run /login"])
def test_auth_error_mid_run_switches_the_brain_off(make, msg):
    fake = FakeCLI([result_line(is_error=True, result=msg)] * 2)
    llm, _ = make(fake)
    with pytest.raises(LLMError):
        llm.json("manager", "S", "T", APPROVAL)
    assert not llm.available and "claude auth login" in llm.reason
    assert len(fake.calls) == 1  # no second paid attempt once auth is known to be broken


def test_api_key_still_wins(make, monkeypatch):
    monkeypatch.setattr(llm_mod, "_has_credentials", lambda: True)
    llm, _ = make(FakeCLI([]))
    assert llm.available and llm.backend == "api"


def test_off_means_off(make):
    llm, _ = make(FakeCLI([]), AGENCY_LLM="off")
    assert not llm.available and llm.backend == ""


# -- the transcript side of running on this laptop ------------------------------------------------
def test_whisper_misspellings_of_the_creator_snap_to_the_brief():
    from noze.agency.media.transcribe import fix_names

    tr = {"segments": [{"text": "Yo chat, skiMaskTimmy here. Skimask timmy? mid",
                        "words": [{"word": "Yo"}, {"word": "chat,"}, {"word": "skiMaskTimmy"}, {"word": "here."},
                                  {"word": "mid"}, {"word": "SkiiMaskTimmy!"}]}]}
    n = fix_names(tr, "SkiiMaskTimmy, skiimasktimmy.")
    words = [w["word"] for w in tr["segments"][0]["words"]]
    assert n == 1 and words == ["Yo", "chat,", "SkiiMaskTimmy", "here.", "mid", "SkiiMaskTimmy!"]
    assert tr["segments"][0]["text"].startswith("Yo chat, SkiiMaskTimmy here.")
    assert fix_names(tr, "") == 0  # no hint, no edits
    short = {"segments": [{"text": "that was sketchy, sketch", "words": [{"word": "sketchy,"}, {"word": "sketch"}]}]}
    fix_names(short, "Sketch")
    assert [w["word"] for w in short["segments"][0]["words"]] == ["sketchy,", "Sketch"]


def test_whisper_device_override(monkeypatch):
    from noze.agency.media import transcribe as t

    monkeypatch.setenv("AGENCY_WHISPER_DEVICE", "cpu")
    assert t._whisper_devices() == ["cpu"]

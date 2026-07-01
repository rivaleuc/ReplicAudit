"""ReplicAudit tests: assessment guards, replication-before-assess enforcement, full submit→replicate→assess flow."""

A = "0xAAa0000000000000000000000000000000000001"
B = "0xBBb0000000000000000000000000000000000002"
C = "0xCCc0000000000000000000000000000000000003"

OUTCOMES = ("replicates", "partial", "fails")


def test_normalize_assessment(contract):
    n = contract.normalize_assessment
    # good inputs
    assert n({"outcome": "replicates", "reasoning": "matches within CI"})["outcome"] == "replicates"
    assert n({"outcome": "PARTIAL", "reasoning": "weaker effect"})["outcome"] == "partial"
    assert n({"outcome": "  Fails  ", "reasoning": "contradicts"})["outcome"] == "fails"
    # adversarial: bad enum -> conservative default 'fails'
    assert n({"outcome": "maybe", "reasoning": "x"})["outcome"] == "fails"
    assert n({"outcome": 42, "reasoning": "x"})["outcome"] == "fails"
    # adversarial: non-dict -> safe default, never raises
    assert n("not a dict")["outcome"] == "fails"
    assert n(None)["outcome"] == "fails"
    assert n([1, 2, 3])["outcome"] == "fails"
    # adversarial: empty / missing reasoning -> filled placeholder, never raises
    assert n({"outcome": "replicates", "reasoning": "   "})["reasoning"] == "no reasoning"
    assert n({"outcome": "replicates"})["reasoning"] == "no reasoning"
    # the shim's empty exec_prompt result must yield a valid default
    assert n({}) == {"outcome": "fails", "reasoning": "no reasoning"}
    # reasoning is trimmed
    assert n({"outcome": "partial", "reasoning": "  mixed evidence  "})["reasoning"] == "mixed evidence"


def test_validate_assessment(contract):
    v = contract.validate_assessment
    # good
    assert v({"outcome": "replicates", "reasoning": "supported"})
    assert v({"outcome": "partial", "reasoning": "mixed"})
    assert v({"outcome": "fails", "reasoning": "contradicts"})
    # adversarial
    assert not v({"outcome": "yes", "reasoning": "x"})           # bad enum
    assert not v({"outcome": "replicates", "reasoning": "   "})  # empty reasoning
    assert not v({"reasoning": "x"})                             # missing outcome
    assert not v({"outcome": "fails", "reasoning": 5})           # reasoning not a string
    assert not v("nope")                                         # non-dict
    assert not v([])                                             # non-dict


def _new(contract):
    return contract, contract.ReplicAudit()


def test_full_audit_flow(contract):
    mod, c = _new(contract)
    # author registers a study
    mod.gl.message.sender_address = A
    sid = c.submit_study(
        "Compound X reduces tumor growth by 40% in mice",
        "Randomized double-blind trial, n=200, 12-week dosing",
        "https://data.example/x",
    )
    assert sid == "0"

    # cannot assess before any replication report exists
    try:
        c.assess(sid); assert False, "should not assess before replication"
    except Exception:
        pass

    # an independent replicator files a report; state stays 'open'
    mod.gl.message.sender_address = B
    r = c.submit_replication(sid, "Independent lab, n=180, observed only 12% reduction", "https://data.example/x-rep")
    assert r["state"] == "open"
    s_open = c.get_study(sid)
    assert s_open["state"] == "open" and s_open["replication"] and s_open["replicator"] == B

    # assess — under the shim, consensus returns the normalized default outcome (in the enum)
    out = c.assess(sid)
    assert out["outcome"] in OUTCOMES
    assert out["outcome"] == "fails"          # shim exec_prompt -> {} -> conservative default

    # finalized state transition + decisive field is within the valid enum
    s = c.get_study(sid)
    assert s["exists"] is True
    assert s["state"] == "assessed"
    assert s["outcome"] in OUTCOMES and s["reasoning"]

    # cannot assess twice
    try:
        c.assess(sid); assert False, "should not re-assess"
    except Exception:
        pass
    # cannot attach a replication after assessment
    try:
        c.submit_replication(sid, "late report", "url"); assert False, "should not replicate after assessed"
    except Exception:
        pass

    st = c.stats()
    assert st["total_studies"] == 1 and st["assessed"] == 1
    mod.gl.message.sender_address = A


def test_guards_and_unknown_ids(contract):
    mod, c = _new(contract)
    mod.gl.message.sender_address = A
    # missing id -> view returns exists False
    assert c.get_study("999") == {"exists": False}
    # empty required fields rejected
    try:
        c.submit_study("   ", "methods", "url"); assert False, "empty claim rejected"
    except Exception:
        pass
    # unknown study guards on writes
    try:
        c.submit_replication("999", "report", "url"); assert False, "unknown study rejected"
    except Exception:
        pass
    try:
        c.assess("999"); assert False, "unknown study rejected"
    except Exception:
        pass
    # empty replication report rejected
    sid = c.submit_study("Claim", "Methods", "url")
    try:
        c.submit_replication(sid, "   ", "url"); assert False, "empty report rejected"
    except Exception:
        pass
    mod.gl.message.sender_address = A

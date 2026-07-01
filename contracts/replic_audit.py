# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
ReplicAudit — a research-reproducibility registry, judged by GenLayer validator consensus.

An author registers a study (a claim + the methods + a link to the data). An
independent replicator later files a replication report (what they observed when
they re-ran the methods). `assess` then has every validator independently compare
the original claim against the replication and decide a single verdict — the
result is accepted only when validators agree on the OUTCOME enum
(`replicates` / `partial` / `fails`), not on the wording of the reasoning.

The verb is "decide whether an independent replication reproduces a claimed
result" — distinct from scoring a debate or ranking entries; it is a one-shot
reproducibility audit of one study against one replication report.
"""
import json
from genlayer import *

OUTCOMES = ("replicates", "partial", "fails")


def normalize_assessment(raw) -> dict:
    """Coerce raw model output into a valid assessment. Never raises; `{}` -> safe default."""
    if not isinstance(raw, dict):
        raw = {}
    outcome = str(raw.get("outcome", "")).strip().lower()
    if outcome not in OUTCOMES:
        outcome = "fails"             # conservative default when unclear
    reasoning = raw.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        reasoning = "no reasoning"
    return {"outcome": outcome, "reasoning": reasoning.strip()[:600]}


def validate_assessment(data) -> bool:
    """Enforce the decisive-enum + non-empty-reasoning invariants."""
    if not isinstance(data, dict):
        return False
    if data.get("outcome") not in OUTCOMES:
        return False
    r = data.get("reasoning")
    return isinstance(r, str) and bool(r.strip())


class ReplicAudit(gl.Contract):
    studies: TreeMap[str, str]
    study_count: u256
    assessed_count: u256

    def __init__(self):
        self.study_count = u256(0)
        self.assessed_count = u256(0)

    # ----------------------------------------------------------- submit study
    @gl.public.write
    def submit_study(self, claim: str, methods: str, data_url: str) -> str:
        claim = str(claim).strip()
        methods = str(methods).strip()
        data_url = str(data_url).strip()
        if not claim or not methods:
            raise Exception("claim and methods required")
        key = str(int(self.study_count))
        rec = {
            "author": str(gl.message.sender_address),
            "claim": claim[:600],
            "methods": methods[:1500],
            "data_url": data_url[:300],
            "replication": "",
            "result_url": "",
            "replicator": "",
            "state": "open",          # open -> assessed
            "outcome": "",
            "reasoning": "",
        }
        self.studies[key] = json.dumps(rec)
        self.study_count += u256(1)
        return key

    # ----------------------------------------------------------- submit replication
    @gl.public.write
    def submit_replication(self, study_id: str, report: str, result_url: str) -> dict:
        """Attach an independent replication report. State stays 'open' until assessed."""
        study_id = str(study_id)
        if study_id not in self.studies:
            raise Exception("unknown study")
        s = json.loads(self.studies[study_id])
        if s["state"] != "open":
            raise Exception("study already assessed")
        report = str(report).strip()
        result_url = str(result_url).strip()
        if not report:
            raise Exception("replication report required")
        s["replication"] = report[:1500]
        s["result_url"] = result_url[:300]
        s["replicator"] = str(gl.message.sender_address)
        self.studies[study_id] = json.dumps(s)            # state stays 'open'
        return {"study": study_id, "state": s["state"]}

    # ----------------------------------------------------------- assess
    @gl.public.write
    def assess(self, study_id: str) -> dict:
        """Consensus compares the claim against the replication and decides the outcome."""
        study_id = str(study_id)
        if study_id not in self.studies:
            raise Exception("unknown study")
        s = json.loads(self.studies[study_id])
        if s["state"] != "open":
            raise Exception("study already assessed")
        if not str(s.get("replication", "")).strip():
            raise Exception("a replication report is required before assessment")

        result = self._assess(s["claim"], s["methods"], s["replication"])
        s["outcome"] = result["outcome"]
        s["reasoning"] = result["reasoning"]
        s["state"] = "assessed"
        self.studies[study_id] = json.dumps(s)
        self.assessed_count += u256(1)
        return {"study": study_id, "outcome": result["outcome"]}

    def _assess(self, claim: str, methods: str, replication: str) -> dict:
        def do_assess() -> str:
            prompt = f"""You are an impartial reproducibility auditor. Decide whether an independent replication reproduces the original study's claimed result.

ORIGINAL CLAIM: {claim}

ORIGINAL METHODS: {methods}

REPLICATION REPORT: {replication}

Judge ONLY whether the replication reproduces the claim:
- "replicates": the replication clearly supports the claim.
- "partial": mixed or weaker support, but not a contradiction.
- "fails": the replication does not support, or contradicts, the claim.
Base it on the evidence in the report, not on your own prior beliefs.
Reply ONLY JSON: {{"outcome":"replicates|partial|fails","reasoning":"<short>"}}"""
            raw = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(raw, dict):
                try:
                    raw = json.loads(str(raw))
                except Exception:
                    raw = {}
            return json.dumps(normalize_assessment(raw))

        result = gl.eq_principle.prompt_comparative(
            do_assess,
            principle="The outcome enum (replicates / partial / fails) must be identical across validators; reasoning wording may differ.",
        )
        data = json.loads(result) if isinstance(result, str) else result
        if not validate_assessment(data):
            data = normalize_assessment(data if isinstance(data, dict) else {})
        return data

    # ----------------------------------------------------------- views
    @gl.public.view
    def get_study(self, study_id: str) -> dict:
        study_id = str(study_id)
        if study_id not in self.studies:
            return {"exists": False}
        s = json.loads(self.studies[study_id])
        s["exists"] = True
        return s

    @gl.public.view
    def stats(self) -> dict:
        return {"total_studies": int(self.study_count), "assessed": int(self.assessed_count)}

from __future__ import annotations

from ultra_trace.core.findings import ProofArtifact
from ultra_trace.frontend.models import SourceSpan


def proof_for_force_unwrap(
    *,
    location: SourceSpan,
    symbol_name: str,
    operand_name: str | None,
    path_summary: str,
    high: bool,
) -> ProofArtifact:
    name = operand_name or "the optional value"
    trigger = (
        f"Call `{symbol_name}` such that `{name}` is nil, reaching "
        f"{location.file_path}:{location.start_line}."
    )
    steps = (
        f"1. Enter `{symbol_name}` with `{name}` = nil.\n"
        f"2. Follow path: {path_summary}\n"
        f"3. Execute the force unwrap at line {location.start_line}.\n"
        "4. Observe a runtime crash (EXC_BAD_INSTRUCTION / unexpectedly found nil)."
    )
    if high:
        return ProofArtifact(
            tier=2,
            kind="repro_steps",
            supported=True,
            trigger_condition=trigger,
            expected_behavior="Process crashes on force unwrap of a nil optional.",
            assumptions=(
                "Local intra-procedural facts only; no callee descent.",
                f"`{name}` is optional and not proven non-nil on this path.",
            ),
            content=steps,
            language="text",
        )
    return ProofArtifact(
        tier=3,
        kind="path_witness",
        supported=True,
        trigger_condition=trigger,
        expected_behavior="Force unwrap may crash if the value is nil.",
        assumptions=("Nilness is uncertain on at least one explored path.",),
        content=steps,
        language="text",
    )


def write_proof_file(path: object, artifact: ProofArtifact, finding_id: str) -> None:
    from pathlib import Path

    dest = Path(str(path))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        f"# Proof {finding_id}\n\n"
        f"- Tier: {artifact.tier}\n"
        f"- Kind: {artifact.kind}\n"
        f"- Supported: {artifact.supported}\n\n"
        f"## Trigger\n{artifact.trigger_condition}\n\n"
        f"## Expected\n{artifact.expected_behavior}\n\n"
        f"## Steps\n{artifact.content}\n",
        encoding="utf-8",
    )

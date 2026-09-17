"""REPL session state: warm analysis once, then slash / ask turns."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, TextIO

from ultra_trace.config import UltraTraceConfig
from ultra_trace.core.findings import Finding
from ultra_trace.engine.pipeline import AnalysisResult, analyze_repository
from ultra_trace.frontend.models import FrontendSymbol, flatten_symbols
from ultra_trace.llm.candidates import is_llm_proposed, request_candidate_findings
from ultra_trace.llm.privacy import AssistPolicy, policy_from_config
from ultra_trace.llm.provider import LLMProvider
from ultra_trace.llm.session import LLMSession
from ultra_trace.repl.parse import parse_repl_line
from ultra_trace.reporting.ordering import sort_findings
from ultra_trace.reporting.writers import write_reports

ASK_TURN_LIMIT = 20
ASSIST_BANNER = (
    "Assist mode (ultra): Core + advanced packs. "
    "LLM advisory only. Analyzer owns findings, severity, and proofs. "
    "Concurrency findings are pattern witnesses, not race-freedom."
)


@dataclass
class ReplSession:
    repo_root: Path
    cfg: UltraTraceConfig
    result: AnalysisResult
    output_dir: Path
    output_basename: str = "ultra-trace-repl-report"
    fail_on_parser_drift: bool = False
    provider: LLMProvider | None = None
    policy: AssistPolicy | None = None
    selected_alias: str | None = None
    selected_finding_id: str | None = None
    focus_symbol: str | None = None
    ask_turns_used: int = 0
    recent_turns: list[tuple[str, str]] = field(default_factory=list)
    _alias_to_id: dict[str, str] = field(default_factory=dict)
    _id_to_alias: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.policy is None:
            self.policy = policy_from_config(self.cfg)
        self._rebuild_aliases()

    def _rebuild_aliases(self) -> None:
        ordered = sort_findings(self.result.findings)
        self._alias_to_id = {}
        self._id_to_alias = {}
        for index, finding in enumerate(ordered, start=1):
            alias = f"F{index}"
            self._alias_to_id[alias.lower()] = finding.id
            self._alias_to_id[alias] = finding.id
            self._id_to_alias[finding.id] = alias

    @property
    def llm_available(self) -> bool:
        return (
            self.cfg.llm.enabled
            and self.policy is not None
            and self.policy.active
            and self.provider is not None
        )

    def ordered_findings(self) -> tuple[Finding, ...]:
        return sort_findings(self.result.findings)

    def resolve_finding(self, token: str) -> Finding | None:
        key = token.strip()
        if not key:
            return None
        finding_id = self._alias_to_id.get(key) or self._alias_to_id.get(key.upper())
        if finding_id is None and key in self._id_to_alias:
            finding_id = key
        if finding_id is None:
            # Accept full id case-sensitively.
            for finding in self.result.findings:
                if finding.id == key:
                    finding_id = finding.id
                    break
        if finding_id is None:
            return None
        for finding in self.result.findings:
            if finding.id == finding_id:
                return finding
        return None

    def select_finding(self, finding: Finding) -> None:
        self.selected_finding_id = finding.id
        self.selected_alias = self._id_to_alias.get(finding.id)

    def alias_for(self, finding: Finding) -> str:
        return self._id_to_alias.get(finding.id, finding.id)

    def match_symbols(
        self, query: str, *, limit: int = 20
    ) -> tuple[FrontendSymbol, ...]:
        needle = query.strip().lower()
        if not needle:
            return ()
        hits: list[FrontendSymbol] = []
        for file in self.result.unit.files:
            for symbol in flatten_symbols(file.top_level_symbols):
                if (
                    needle in symbol.name.lower()
                    or needle in symbol.qualified_name.lower()
                ):
                    hits.append(symbol)
                    if len(hits) >= limit:
                        return tuple(hits)
        return tuple(hits)

    def findings_for_symbol(self, query: str) -> tuple[Finding, ...]:
        needle = query.strip().lower()
        return tuple(
            f
            for f in self.ordered_findings()
            if (f.symbol_name and needle in f.symbol_name.lower())
            or (f.symbol_id and needle in f.symbol_id.lower())
        )

    def export_reports(self, dest: Path | None = None) -> list[str]:
        out = dest or self.output_dir
        written = write_reports(
            output_dir=out,
            basename=self.output_basename,
            formats=self.cfg.output_formats,
            repo_root=self.repo_root,
            files_discovered=self.result.files_discovered,
            result=self.result,
            privacy_mode=self.cfg.privacy_mode,
            severity_threshold=self.cfg.severity_threshold,
            max_depth=self.cfg.max_depth,
            llm_enabled=self.cfg.llm.enabled,
            analysis_modes=self.cfg.analysis_modes,
            analysis_target_language=self.cfg.target_language,
        )
        paths: list[str] = []
        if written.markdown_path:
            paths.append(str(written.markdown_path))
        if written.json_path:
            paths.append(str(written.json_path))
        if written.sarif_path:
            paths.append(str(written.sarif_path))
        for proof in written.proof_paths:
            paths.append(str(proof))
        return paths

    def reload(self) -> None:
        self.result = analyze_repository(
            self.repo_root,
            self.cfg,
            validate_helper=self.cfg.target_language == "swift",
            fail_on_parser_drift=self.fail_on_parser_drift,
        )
        self._rebuild_aliases()
        self.selected_finding_id = None
        self.selected_alias = None

    def refresh_candidates(self) -> tuple[Finding, ...]:
        if not self.llm_available or self.provider is None or self.policy is None:
            return ()
        proposed = request_candidate_findings(
            self.provider,
            self.result.findings,
            self.policy,
            unit=self.result.unit,
        )
        if not proposed:
            return ()
        existing_ids = {f.id for f in self.result.findings}
        new_items = tuple(f for f in proposed if f.id not in existing_ids)
        if not new_items:
            return ()
        # Append only; never mutate severity or fields on analyzer findings.
        merged = tuple(
            sorted(
                (*self.result.findings, *new_items),
                key=lambda f: (
                    f.location.file_path,
                    f.location.start_line,
                    f.location.start_column,
                    f.id,
                ),
            )
        )
        self.result = replace(self.result, findings=merged)
        self._rebuild_aliases()
        return new_items

    def proposed_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.ordered_findings() if is_llm_proposed(f))

    def note_ask_turn(self, question: str, answer: str) -> None:
        self.ask_turns_used += 1
        self.recent_turns.append((question, answer))
        if len(self.recent_turns) > 6:
            self.recent_turns = self.recent_turns[-6:]


def warm_repl_session(
    *,
    repo_root: Path,
    cfg: UltraTraceConfig,
    output_dir: Path,
    output_basename: str = "ultra-trace-repl-report",
    fail_on_parser_drift: bool = False,
    environ: dict[str, str] | None = None,
    provider: LLMProvider | None = None,
) -> ReplSession:
    result = analyze_repository(
        repo_root,
        cfg,
        validate_helper=cfg.target_language == "swift",
        fail_on_parser_drift=fail_on_parser_drift,
    )
    session_llm = LLMSession(cfg, environ=environ, provider=provider)
    return ReplSession(
        repo_root=repo_root,
        cfg=cfg,
        result=result,
        output_dir=output_dir,
        output_basename=output_basename,
        fail_on_parser_drift=fail_on_parser_drift,
        provider=provider if provider is not None else session_llm.provider,
        policy=session_llm.policy,
    )


def run_repl(
    session: ReplSession,
    *,
    stdout: TextIO | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> int:
    """Run the interactive loop. Returns process exit code (always 0 on quit)."""
    import sys

    from ultra_trace.repl.commands import dispatch_command

    out = stdout or sys.stdout
    read = input_fn
    if read is None:

        def read(prompt: str) -> str:
            return input(prompt)

    print(ASSIST_BANNER, file=out)
    print(
        f"Warmed {session.result.files_discovered} file(s); "
        f"{len(session.result.findings)} finding(s). Type /help.",
        file=out,
    )
    while True:
        try:
            line = read("ultra-trace> ")
        except EOFError:
            print("", file=out)
            return 0
        except KeyboardInterrupt:
            print("\n(interrupted — type /quit to exit)", file=out)
            continue
        parsed = parse_repl_line(line)
        if parsed is None:
            continue
        message, should_quit = dispatch_command(session, parsed)
        if message:
            print(message, file=out)
        if should_quit:
            return 0

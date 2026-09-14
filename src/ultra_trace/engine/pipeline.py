from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from ultra_trace.advanced.availability import AdvancedStatus, resolve_advanced_status
from ultra_trace.advanced.sil_explorer import run_sil_exploration
from ultra_trace.cfg.builder import CFGBuilder
from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.config import CallSummaryConfig, UltraTraceConfig
from ultra_trace.core.findings import Finding
from ultra_trace.discovery.scanner import RepositoryFile, default_scanner
from ultra_trace.engine.explorer import PathExplorer
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit, flatten_symbols
from ultra_trace.frontend.sdk_effects import SDKEffectCatalog
from ultra_trace.frontend.summaries import make_summary_provider
from ultra_trace.llm.models import ExplorationPlan, LLMRunMetadata
from ultra_trace.llm.network import block_network
from ultra_trace.llm.session import LLMSession
from ultra_trace.parser.helper import invoke_helper
from ultra_trace.rules.pack import rules_for_language
from ultra_trace.swift_frontend import normalize_helper_output
from ultra_trace.taint.catalog import TaintCatalog
from ultra_trace.taint.defaults import (
    STARTER_SANITIZER_PATTERNS,
    STARTER_SINK_PATTERNS,
    STARTER_SOURCE_PATTERNS,
)


@dataclass(frozen=True)
class AnalysisResult:
    unit: FrontendUnit
    findings: tuple[Finding, ...]
    paths_explored: int
    functions_analyzed: int
    graphs: tuple[ControlFlowGraph, ...]
    files_discovered: int
    llm: LLMRunMetadata | None = None
    resolved_plan: ExplorationPlan | None = None
    advanced: AdvancedStatus | None = None


def analyze_unit(
    unit: FrontendUnit,
    *,
    max_depth: int,
    files_discovered: int | None = None,
    taint_catalog: TaintCatalog | None = None,
    call_summary: CallSummaryConfig | None = None,
    sdk_catalog: SDKEffectCatalog | None = None,
    rule_packs: tuple[str, ...] = ("core",),
    target_language: str = "swift",
) -> AnalysisResult:
    catalog = taint_catalog or (
        TaintCatalog.python() if target_language == "python" else TaintCatalog.starter()
    )
    summary_cfg = call_summary or CallSummaryConfig()
    sdk = sdk_catalog
    if summary_cfg.enabled and sdk is None:
        sdk = SDKEffectCatalog.default()
    builder = CFGBuilder()
    summaries = make_summary_provider(
        unit,
        enabled=summary_cfg.enabled,
        max_depth=summary_cfg.max_depth,
        sdk_catalog=sdk,
    )
    explorer = PathExplorer(
        max_depth=max_depth, summaries=summaries, taint_catalog=catalog
    )
    rules = rules_for_language(target_language, rule_packs, catalog)
    findings: list[Finding] = []
    graphs: list[ControlFlowGraph] = []
    path_count = 0
    analyzed = 0

    symbols = [
        s
        for f in unit.files
        for s in flatten_symbols(f.top_level_symbols)
        if s.body is not None
        and s.eligibility.state in {"cfg-ready", "partially-analyzed"}
    ]
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[FrontendSymbol] = []
    for sym in symbols:
        if sym.symbol_id in seen:
            continue
        seen.add(sym.symbol_id)
        unique.append(sym)

    for symbol in unique:
        if symbol.body is None or not symbol.body.location.is_valid():
            continue
        if symbol.eligibility.state not in {"cfg-ready", "partially-analyzed"}:
            continue
        graph = builder.build(symbol)
        graphs.append(graph)
        explored = explorer.explore(symbol, graph)
        path_count += explored.path_count
        analyzed += 1
        for rule in rules:
            findings.extend(
                rule.evaluate(symbol=symbol, cfg=graph, exploration=explored, unit=unit)
            )

    findings.sort(
        key=lambda f: (
            f.location.file_path,
            f.location.start_line,
            f.location.start_column,
            f.id,
        )
    )
    return AnalysisResult(
        unit=unit,
        findings=tuple(findings),
        paths_explored=path_count,
        functions_analyzed=analyzed,
        graphs=tuple(graphs),
        files_discovered=files_discovered
        if files_discovered is not None
        else len(unit.files),
    )


def analyze_repository(
    repo_root: Path,
    cfg: UltraTraceConfig,
    *,
    files: Sequence[RepositoryFile] | None = None,
    validate_helper: bool = True,
    fail_on_parser_drift: bool = False,
) -> AnalysisResult:
    offline = cfg.privacy_mode == "offline"
    ctx = block_network() if offline else nullcontext()
    with ctx:
        return _analyze_repository_inner(
            repo_root,
            cfg,
            files=files,
            validate_helper=validate_helper,
            fail_on_parser_drift=fail_on_parser_drift,
        )


def _analyze_repository_inner(
    repo_root: Path,
    cfg: UltraTraceConfig,
    *,
    files: Sequence[RepositoryFile] | None,
    validate_helper: bool,
    fail_on_parser_drift: bool,
) -> AnalysisResult:
    language = cfg.target_language
    scanner = default_scanner()
    if files is not None:
        discovered = list(files)
    elif language == "python":
        from ultra_trace.discovery.scanner import PYTHON_EXCLUDES

        excludes = cfg.exclude_paths
        if excludes == UltraTraceConfig().exclude_paths:
            excludes = PYTHON_EXCLUDES
        discovered = scanner.discover_python_files(
            repo_root,
            include_paths=cfg.include_paths,
            exclude_paths=excludes,
        )
    else:
        discovered = scanner.discover_swift_files(
            repo_root,
            include_paths=cfg.include_paths,
            exclude_paths=cfg.exclude_paths,
        )
    session = LLMSession(cfg)
    plan = session.resolve_plan()
    advanced_requested = "advanced" in cfg.analysis_modes and language == "swift"
    catalog = _taint_catalog_for(cfg)
    if language == "python":
        return _analyze_python_repository(
            repo_root,
            cfg,
            discovered=discovered,
            session=session,
            plan=plan,
            catalog=catalog,
        )

    if not discovered:
        empty = normalize_helper_output(
            {
                "schema_version": "1.0",
                "parser_metadata": {"parser_name": "swift-parser-helper"},
                "files": [],
            }
        )
        result = analyze_unit(
            empty,
            max_depth=plan.max_depth,
            files_discovered=0,
            taint_catalog=catalog,
            call_summary=cfg.call_summary,
            rule_packs=cfg.rule_packs,
            target_language=language,
        )
        advanced = resolve_advanced_status(
            requested=advanced_requested,
            advanced_enabled=cfg.advanced.enabled or advanced_requested,
            sil_toolchain_path=cfg.advanced.sil_toolchain_path,
            sil_pipeline_ready=True,
        )
        return replace(
            result,
            llm=session.metadata_after(plan, result.findings),
            resolved_plan=plan,
            advanced=advanced,
        )

    helper = invoke_helper(
        repo_root=repo_root,
        files=[f.path for f in discovered],
        configured_path=cfg.swift_frontend.helper_path,
        configured_parser_version=cfg.swift_frontend.parser_version,
        timeout_seconds=float(cfg.swift_frontend.helper_timeout_seconds),
        validate=validate_helper,
        fail_on_parser_drift=fail_on_parser_drift,
    )
    unit = normalize_helper_output(helper.payload)
    result = analyze_unit(
        unit,
        max_depth=plan.max_depth,
        files_discovered=len(discovered),
        taint_catalog=catalog,
        call_summary=cfg.call_summary,
        rule_packs=cfg.rule_packs,
        target_language=language,
    )
    if advanced_requested:
        sil = run_sil_exploration(
            unit=unit,
            source_files=[repo_root / f.path for f in discovered],
            requested=True,
            advanced_enabled=cfg.advanced.enabled or True,
            sil_toolchain_path=cfg.advanced.sil_toolchain_path,
        )
        findings = tuple(
            sorted(
                (*result.findings, *sil.findings),
                key=lambda f: (
                    f.location.file_path,
                    f.location.start_line,
                    f.location.start_column,
                    f.id,
                ),
            )
        )
        result = replace(result, findings=findings, advanced=sil.status)
    else:
        result = replace(
            result,
            advanced=resolve_advanced_status(
                requested=False,
                advanced_enabled=False,
                sil_pipeline_ready=True,
            ),
        )
    return replace(
        result,
        llm=session.metadata_after(plan, result.findings),
        resolved_plan=plan,
    )


def _taint_catalog_for(cfg: UltraTraceConfig) -> TaintCatalog:
    defaults = UltraTraceConfig()
    using_swift_defaults = (
        cfg.source_patterns == STARTER_SOURCE_PATTERNS
        and cfg.sink_patterns == STARTER_SINK_PATTERNS
        and cfg.sanitizer_patterns == STARTER_SANITIZER_PATTERNS
    )
    if cfg.target_language == "python" and using_swift_defaults:
        catalog = TaintCatalog.python()
    else:
        catalog = TaintCatalog.from_patterns(
            sources=cfg.source_patterns,
            sinks=cfg.sink_patterns,
            sanitizers=cfg.sanitizer_patterns,
        )
    if "advanced" in cfg.rule_packs and cfg.target_language == "swift":
        catalog = catalog.merged_with(TaintCatalog.advanced())
    del defaults
    return catalog


def _analyze_python_repository(
    repo_root: Path,
    cfg: UltraTraceConfig,
    *,
    discovered: list[RepositoryFile],
    session: LLMSession,
    plan: object,
    catalog: TaintCatalog,
) -> AnalysisResult:
    from ultra_trace.llm.models import ExplorationPlan
    from ultra_trace.python_frontend import normalize_python_sources

    assert isinstance(plan, ExplorationPlan)
    if not discovered:
        unit = normalize_python_sources([], repo_root=repo_root)
    else:
        unit = normalize_python_sources(
            [f.path for f in discovered],
            repo_root=repo_root,
        )
    result = analyze_unit(
        unit,
        max_depth=plan.max_depth,
        files_discovered=len(discovered),
        taint_catalog=catalog,
        call_summary=cfg.call_summary,
        rule_packs=cfg.rule_packs,
        target_language="python",
    )
    return replace(
        result,
        llm=session.metadata_after(plan, result.findings),
        resolved_plan=plan,
        advanced=resolve_advanced_status(
            requested=False,
            advanced_enabled=False,
            sil_pipeline_ready=False,
        ),
    )

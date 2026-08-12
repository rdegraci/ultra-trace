from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Sequence

from ultra_trace.cfg.builder import CFGBuilder
from ultra_trace.cfg.models import ControlFlowGraph
from ultra_trace.config import UltraTraceConfig
from ultra_trace.core.findings import Finding
from ultra_trace.discovery.scanner import RepositoryFile, default_scanner
from ultra_trace.engine.explorer import ExplorationResult, PathExplorer
from ultra_trace.frontend.models import FrontendSymbol, FrontendUnit, flatten_symbols
from ultra_trace.frontend.summaries import LocalUnknownSummaryProvider
from ultra_trace.llm.models import LLMRunMetadata
from ultra_trace.llm.session import LLMSession
from ultra_trace.parser.helper import invoke_helper
from ultra_trace.rules.pack import core_rules
from ultra_trace.swift_frontend import normalize_helper_output
from ultra_trace.taint.catalog import TaintCatalog


@dataclass(frozen=True)
class AnalysisResult:
    unit: FrontendUnit
    findings: tuple[Finding, ...]
    paths_explored: int
    functions_analyzed: int
    graphs: tuple[ControlFlowGraph, ...]
    files_discovered: int
    llm: LLMRunMetadata | None = None


def analyze_unit(
    unit: FrontendUnit,
    *,
    max_depth: int,
    files_discovered: int | None = None,
    taint_catalog: TaintCatalog | None = None,
) -> AnalysisResult:
    catalog = taint_catalog or TaintCatalog.starter()
    builder = CFGBuilder()
    summaries = LocalUnknownSummaryProvider(dict(unit.symbols_by_id))
    explorer = PathExplorer(
        max_depth=max_depth, summaries=summaries, taint_catalog=catalog
    )
    rules = core_rules(catalog)
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
                rule.evaluate(
                    symbol=symbol, cfg=graph, exploration=explored, unit=unit
                )
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
        files_discovered=files_discovered if files_discovered is not None else len(unit.files),
    )


def analyze_repository(
    repo_root: Path,
    cfg: UltraTraceConfig,
    *,
    files: Sequence[RepositoryFile] | None = None,
    validate_helper: bool = True,
    fail_on_parser_drift: bool = False,
) -> AnalysisResult:
    scanner = default_scanner()
    discovered = (
        list(files)
        if files is not None
        else scanner.discover_swift_files(
            repo_root,
            include_paths=cfg.include_paths,
            exclude_paths=cfg.exclude_paths,
        )
    )
    session = LLMSession(cfg)
    plan = session.resolve_plan()
    catalog = TaintCatalog.from_patterns(
        sources=cfg.source_patterns,
        sinks=cfg.sink_patterns,
        sanitizers=cfg.sanitizer_patterns,
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
        )
        return replace(result, llm=session.metadata_after(plan, result.findings))

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
    )
    return replace(result, llm=session.metadata_after(plan, result.findings))

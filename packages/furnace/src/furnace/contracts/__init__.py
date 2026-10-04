"""Furnace contracts: the single source of truth for cross-component data shapes.

TypeScript types for the web app are generated from the API's OpenAPI schema,
which is built from these models.
"""

from furnace_bench.schema import BenchPlan, BenchReport, BenchTarget
from furnace_bench.workload_spec import WorkloadSpec

from furnace.contracts.appspec import AppSpec
from furnace.contracts.blueprint import Blueprint, Recommendation
from furnace.contracts.common import Claim, Evidence, EvidenceSourceKind, Locator
from furnace.contracts.evals import Evaluator, FailureMode
from furnace.contracts.graph import EdgeKind, Graph, GraphEdge, GraphNode, NodeKind
from furnace.contracts.guard import ForgePlan, PRImpact, RepairAttempt

__all__ = [
    "AppSpec",
    "BenchPlan",
    "BenchReport",
    "BenchTarget",
    "Blueprint",
    "Claim",
    "EdgeKind",
    "Evaluator",
    "Evidence",
    "EvidenceSourceKind",
    "FailureMode",
    "ForgePlan",
    "Graph",
    "GraphEdge",
    "GraphNode",
    "Locator",
    "NodeKind",
    "PRImpact",
    "Recommendation",
    "RepairAttempt",
    "WorkloadSpec",
]

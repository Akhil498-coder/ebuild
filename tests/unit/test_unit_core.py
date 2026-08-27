# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EoS Project

"""Unit tests for the build dependency graph.

These tests import only ebuild.core.graph (no yaml/click) so they run on a
bare Python install. They replace a previous placeholder that did not
exercise the graph at all.
"""

from types import SimpleNamespace

import pytest

from ebuild.core.graph import (
    CycleError,
    DependencyGraph,
    build_dependency_graph,
)


class TestDependencyGraph:
    def test_empty_graph(self):
        assert DependencyGraph().topological_sort() == []

    def test_single_node(self):
        graph = DependencyGraph()
        graph.add_node("app")
        assert graph.topological_sort() == ["app"]

    def test_linear_chain(self):
        graph = DependencyGraph()
        graph.add_edge("app", "lib")
        graph.add_edge("lib", "core")
        assert graph.topological_sort() == ["core", "lib", "app"]

    def test_diamond_dependency(self):
        graph = DependencyGraph()
        graph.add_edge("app", "liba")
        graph.add_edge("app", "libb")
        graph.add_edge("liba", "core")
        graph.add_edge("libb", "core")
        assert graph.topological_sort() == ["core", "liba", "libb", "app"]

    def test_independent_nodes_have_stable_order(self):
        """Unrelated targets must come out in sorted order, not hash order.

        Nodes are inserted out of alphabetical order on purpose. Without a
        sorted ready queue the result follows set iteration order, which is
        not part of the language spec and is not alphabetical here.
        """
        graph = DependencyGraph()
        for name in ["z", "m", "a", "y", "b"]:
            graph.add_node(name)
        assert graph.topological_sort() == ["a", "b", "m", "y", "z"]

    def test_cycle_raises(self):
        graph = DependencyGraph()
        graph.add_edge("a", "b")
        graph.add_edge("b", "a")
        with pytest.raises(CycleError, match="a, b"):
            graph.topological_sort()

    def test_self_cycle_raises(self):
        graph = DependencyGraph()
        graph.add_edge("app", "app")
        with pytest.raises(CycleError, match="app"):
            graph.topological_sort()

    def test_all_dependencies_is_transitive(self):
        graph = DependencyGraph()
        graph.add_edge("app", "lib")
        graph.add_edge("lib", "core")
        assert graph.all_dependencies("app") == {"lib", "core"}
        assert graph.all_dependencies("core") == set()

    def test_dependents_of(self):
        graph = DependencyGraph()
        graph.add_edge("app", "lib")
        graph.add_edge("test", "lib")
        assert graph.dependents_of("lib") == {"app", "test"}
        assert graph.dependents_of("app") == set()


class TestBuildDependencyGraph:
    def test_orders_targets_from_config_objects(self):
        targets = [
            SimpleNamespace(name="app", depends=["lib"]),
            SimpleNamespace(name="lib", depends=["core"]),
            SimpleNamespace(name="core", depends=[]),
        ]
        graph = build_dependency_graph(targets)
        assert graph.topological_sort() == ["core", "lib", "app"]

    def test_cycle_in_targets_raises(self):
        targets = [
            SimpleNamespace(name="a", depends=["b"]),
            SimpleNamespace(name="b", depends=["a"]),
        ]
        with pytest.raises(CycleError):
            build_dependency_graph(targets)

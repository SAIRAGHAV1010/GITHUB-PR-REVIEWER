"""
LangGraph wiring for the review pipeline:

              +-> static_analysis --+
              |                      |
context ------+-> security ---------+--> aggregate --> END
              |                      |
              +-> architecture ------+
              |                      |
              +-> code_style --------+

LangGraph runs all four agent nodes concurrently once context_collector
finishes (they share no data dependency), and 'aggregate' only fires once
every incoming branch has completed for that superstep - i.e. LangGraph's
native fan-out/fan-in, no manual asyncio.gather bookkeeping needed.
"""
from __future__ import annotations

from typing import TypedDict

from langgraph.graph import StateGraph, START, END

from app.agents import (
    static_analysis_agent,
    security_agent,
    architecture_agent,
    code_style_agent,
    aggregator,
)
from app.vector_store import retrieve_similar_reviews


class ReviewState(TypedDict, total=False):
    pr_context_block: str
    static_result: str
    security_result: str
    architecture_result: str
    style_result: str
    similar_past_reviews: list[dict]
    aggregated_result: str


def _node_static(state: ReviewState) -> dict:
    return {"static_result": static_analysis_agent.run(state["pr_context_block"])}


def _node_security(state: ReviewState) -> dict:
    return {"security_result": security_agent.run(state["pr_context_block"])}


def _node_architecture(state: ReviewState) -> dict:
    return {"architecture_result": architecture_agent.run(state["pr_context_block"])}


def _node_style(state: ReviewState) -> dict:
    return {"style_result": code_style_agent.run(state["pr_context_block"])}


def _node_retrieve_history(state: ReviewState) -> dict:
    matches = retrieve_similar_reviews(state["pr_context_block"], k=3)
    return {"similar_past_reviews": matches}


def _node_aggregate(state: ReviewState) -> dict:
    result = aggregator.run(
        static_result=state.get("static_result", ""),
        security_result=state.get("security_result", ""),
        architecture_result=state.get("architecture_result", ""),
        style_result=state.get("style_result", ""),
        similar_past_reviews=state.get("similar_past_reviews", []),
    )
    return {"aggregated_result": result}


def build_review_graph():
    graph = StateGraph(ReviewState)

    graph.add_node("static_analysis", _node_static)
    graph.add_node("security", _node_security)
    graph.add_node("architecture", _node_architecture)
    graph.add_node("code_style", _node_style)
    graph.add_node("retrieve_history", _node_retrieve_history)
    graph.add_node("aggregate", _node_aggregate)

    # Fan-out from START (context is already in the initial state, so all
    # five branches can start immediately in the same superstep).
    for node in ("static_analysis", "security", "architecture", "code_style", "retrieve_history"):
        graph.add_edge(START, node)

    # Fan-in: aggregate waits for all five predecessors.
    for node in ("static_analysis", "security", "architecture", "code_style", "retrieve_history"):
        graph.add_edge(node, "aggregate")

    graph.add_edge("aggregate", END)

    return graph.compile()


_compiled_graph = None


def get_review_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_review_graph()
    return _compiled_graph

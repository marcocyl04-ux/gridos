"""
GridOS API — Agent endpoints.

Handles: /agent/chat, /agent/apply, /agent/chat/chain, /agent/write,
/agent/write/graph, /agent/execute-graph
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from core.engine import GridOSKernel
from core.models import AgentIntent, WriteResponse
from core.node_graph import NodeGraph, Coordinator, Executor, Node, NodeType, TypedInterface
from core.intent_parser import IntentParser, validate_with_feedback

from .deps import (
    _classify_model_error,
    _current_kernel,
    _default_kernel,
    _is_completion_signal,
    _normalize_multi_intents,
    _observe_written_cells,
    cloud_config,
    cloud_usage,
    current_kernel_dep,
    generate_agent_preview,
    kernel,
    AuthUser,
    require_user,
    optional_user,
    ChainRequest,
    ChatRequest,
    PreviewApplyRequest,
    NodeGraphRequest,
    MAX_CHAIN_ITERATIONS,
)

router = APIRouter()


@router.post("/agent/chat")
async def chat_with_agent(
    req: ChatRequest,
    user: AuthUser = Depends(require_user),
    k: GridOSKernel = Depends(current_kernel_dep),
):
    cloud_usage.set_request_context(user.id, None)
    if cloud_config.SAAS_MODE:
        try:
            cloud_usage.over_quota_check(user.id)
        except cloud_usage.QuotaExceeded as qe:
            raise HTTPException(status_code=402, detail={
                "message": "Monthly token cap reached for your tier.",
                "usage": qe.summary,
            })
    try:
        return generate_agent_preview(req)
    except HTTPException:
        raise
    except Exception as e:
        kind = _classify_model_error(e)
        if kind == "transient":
            raise HTTPException(
                status_code=503,
                detail="Model provider is temporarily overloaded (tried 4x with backoff). Wait a moment and try again.",
            )
        if kind == "auth":
            raise HTTPException(
                status_code=401,
                detail="The API key for this model was rejected. Update it in Settings.",
            )
        raise HTTPException(status_code=500, detail=f"Agent Error: {str(e)}")


@router.post("/agent/apply")
async def apply_agent_preview(
    req: PreviewApplyRequest,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    if req.intents:
        valid = _normalize_multi_intents(req.intents)
        if not valid:
            raise HTTPException(status_code=400, detail="intents array is empty or malformed.")
        actual_targets = []
        for vi in valid:
            sub_intent = AgentIntent(
                agent_id=req.agent_id,
                target_start_a1=vi["target_cell"],
                data_payload=vi["values"],
                shift_direction=req.shift_direction,
            )
            _, actual = kernel.process_agent_intent(sub_intent, req.sheet)
            actual_targets.append(actual)
        chart = None
        chart_error = None
        if req.chart_spec:
            try:
                chart = kernel.add_chart(req.chart_spec, sheet_name=req.sheet)
            except Exception as e:
                chart_error = f"Chart skipped: {e}"
        out = {
            "status": "Success",
            "sheet": req.sheet or kernel.active_sheet,
            "actual_target": actual_targets[0],
            "actual_targets": actual_targets,
            "intents_applied": len(actual_targets),
            "chart": chart,
        }
        if chart_error:
            out["chart_error"] = chart_error
        return out

    if not req.target_cell or req.values is None:
        raise HTTPException(status_code=400, detail="Provide either (target_cell + values) or an intents array.")
    intent = AgentIntent(
        agent_id=req.agent_id,
        target_start_a1=req.target_cell,
        data_payload=req.values,
        shift_direction=req.shift_direction,
    )
    requested, actual = kernel.process_agent_intent(intent, req.sheet)
    chart = None
    if req.chart_spec:
        try:
            chart = kernel.add_chart(req.chart_spec, sheet_name=req.sheet)
        except Exception as e:
            return {
                "status": "Partial",
                "sheet": req.sheet or kernel.active_sheet,
                "actual_target": actual,
                "chart_error": f"Chart skipped: {e}",
            }
    return {
        "status": "Success" if requested == actual else "Collision Resolved",
        "sheet": req.sheet or kernel.active_sheet,
        "actual_target": actual,
        "chart": chart,
    }


@router.post("/agent/chat/chain")
async def chat_chain(
    req: ChainRequest,
    user: AuthUser = Depends(require_user),
    k: GridOSKernel = Depends(current_kernel_dep),
):
    cloud_usage.set_request_context(user.id, None)
    if cloud_config.SAAS_MODE:
        try:
            cloud_usage.over_quota_check(user.id)
        except cloud_usage.QuotaExceeded as qe:
            raise HTTPException(status_code=402, detail={
                "message": "Monthly token cap reached for your tier.",
                "usage": qe.summary,
            })
    try:
        sheet = req.sheet or kernel.active_sheet
        history = list(req.history)
        steps: list[dict] = []
        current_prompt = req.prompt
        max_iters = max(1, min(req.max_iterations, MAX_CHAIN_ITERATIONS))

        active_plan: Optional[dict] = None

        for iteration in range(max_iters):
            chat_req = ChatRequest(
                prompt=current_prompt,
                history=history,
                scope=req.scope,
                selected_cells=req.selected_cells,
                sheet=sheet,
                model_id=req.model_id,
            )
            preview = generate_agent_preview(chat_req)
            values = preview["values"] or [[""]]
            chart_spec = preview.get("chart_spec")
            proposed_macro = preview.get("proposed_macro")
            macro_error = preview.get("macro_error")
            plan = preview.get("plan")
            multi_intents = preview.get("intents")
            if plan and active_plan is None:
                active_plan = plan

            if multi_intents:
                actual_targets = []
                for mi in multi_intents:
                    sub = AgentIntent(
                        agent_id=preview["agent_id"],
                        target_start_a1=mi["original_request"],
                        data_payload=mi["values"],
                        shift_direction="right",
                    )
                    _, actual = kernel.process_agent_intent(sub, sheet)
                    actual_targets.append(actual)
                observations = _observe_written_cells(preview["preview_cells"], sheet)
                chart = None
                chart_error = None
                if chart_spec:
                    try:
                        chart = kernel.add_chart(chart_spec, sheet_name=sheet)
                    except Exception as e:
                        chart_error = str(e)
                steps.append({
                    "iteration": iteration,
                    "agent_id": preview["agent_id"],
                    "reasoning": preview["reasoning"],
                    "target": actual_targets[0],
                    "values": None,
                    "intents": multi_intents,
                    "intents_applied": len(actual_targets),
                    "observations": observations,
                    "completion_signal": True,
                    "chart": chart,
                    "chart_error": chart_error,
                    "proposed_macro": proposed_macro,
                    "macro_error": macro_error,
                    "plan": plan,
                })
                break

            skip_cell_write = preview["values"] is None and (chart_spec is not None or proposed_macro is not None)

            if _is_completion_signal(values) and not skip_cell_write:
                steps.append({
                    "iteration": iteration,
                    "agent_id": preview["agent_id"],
                    "reasoning": preview["reasoning"],
                    "target": preview["original_request"],
                    "values": values,
                    "observations": [],
                    "completion_signal": True,
                    "proposed_macro": proposed_macro,
                    "macro_error": macro_error,
                    "plan": plan,
                })
                break

            if skip_cell_write:
                actual_target = preview["original_request"]
                observations = []
                formula_observations = []
            else:
                intent = AgentIntent(
                    agent_id=preview["agent_id"],
                    target_start_a1=preview["original_request"],
                    data_payload=values,
                    shift_direction="right",
                )
                _, actual_target = kernel.process_agent_intent(intent, sheet)
                observations = _observe_written_cells(preview["preview_cells"], sheet)
                formula_observations = [o for o in observations if o["formula"]]

            chart = None
            chart_error = None
            if chart_spec:
                try:
                    chart = kernel.add_chart(chart_spec, sheet_name=sheet)
                except Exception as e:
                    chart_error = str(e)

            steps.append({
                "iteration": iteration,
                "agent_id": preview["agent_id"],
                "reasoning": preview["reasoning"],
                "target": actual_target,
                "values": values,
                "observations": observations,
                "completion_signal": False,
                "chart": chart,
                "chart_error": chart_error,
                "proposed_macro": proposed_macro,
                "macro_error": macro_error,
                "plan": plan,
            })

            assistant_payload = {
                "reasoning": preview["reasoning"],
                "target": actual_target,
                "values": values,
            }
            if plan:
                assistant_payload["plan"] = plan

            history.append({"role": "user", "content": current_prompt})
            history.append({"role": "assistant", "content": json.dumps(assistant_payload)})

            non_completion_steps = [s for s in steps if not s.get("completion_signal")]
            sections_written = sum(
                1
                for s in non_completion_steps
                if not any(o.get("warning") for o in s.get("observations", []))
            )
            plan_sections_total = len(active_plan.get("sections", [])) if active_plan else 0
            plan_remaining = plan_sections_total - sections_written
            has_plan_work = plan_remaining > 0
            has_retry_work = any(o.get("warning") for o in observations)
            if not formula_observations and not has_plan_work and not has_retry_work:
                break

            obs_part = ""
            if formula_observations:
                summary = ", ".join(f"{o['cell']}={o['value']}" for o in formula_observations)
                obs_part = f"Observed after last write: [{summary}]. "

            warning_obs = [o for o in observations if o.get("warning")]
            warning_part = ""
            if warning_obs:
                bullets = "\n".join(f"- {o['warning']}" for o in warning_obs)
                warning_part = (
                    "\n\n*** COLUMN ALIGNMENT WARNINGS — YOU MUST FIX THESE BEFORE MOVING ON ***\n"
                    f"{bullets}\n"
                    "Re-emit the SAME section (same target cell) with corrected formulas. "
                    "Each formula in column X must reference cells in column X, not a label column. "
                    "Do NOT move to the next section until the current section has no warnings.\n\n"
                )

            plan_part = ""
            if has_plan_work:
                next_section = active_plan["sections"][sections_written] if sections_written < plan_sections_total else None
                next_hint = ""
                if next_section:
                    bits = []
                    if next_section.get("label"):
                        bits.append(f"label \"{next_section['label']}\"")
                    if next_section.get("target"):
                        bits.append(f"target range {next_section['target']}")
                    if next_section.get("notes"):
                        bits.append(f"notes: {next_section['notes']}")
                    if bits:
                        label = "The section to (re-)write is" if has_retry_work else "The next section is"
                        next_hint = f" {label}: " + "; ".join(bits) + "."
                verb = "re-emit" if has_retry_work else "write"
                plan_part = (
                    f"You declared a {plan_sections_total}-section plan on turn 1. "
                    f"{sections_written} section(s) have been written cleanly so far. "
                    f"{plan_remaining} section(s) remain (or need retry).{next_hint} "
                    f"{verb.capitalize()} ONLY that one section now. "
                    "Do NOT re-emit the plan (set plan=null). "
                    "When every section is done, signal completion by returning values=[[\"\"]]."
                )

            current_prompt = (
                warning_part
                + obs_part
                + plan_part
                + " If the ORIGINAL task has more targets left to write, produce the next one now and do NOT "
                "repeat cells you have already written. If every part of the original task is done, signal "
                "completion by returning values=[[\"\"]] with target_cell equal to the last written cell."
            )

        return {
            "sheet": sheet,
            "steps": steps,
            "iterations_used": len(steps),
            "terminated_early": len(steps) < max_iters,
        }
    except HTTPException:
        raise
    except Exception as e:
        kind = _classify_model_error(e)
        if kind == "transient":
            raise HTTPException(
                status_code=503,
                detail="Model provider is temporarily overloaded (tried 4x with backoff). Wait a moment and try again.",
            )
        if kind == "auth":
            raise HTTPException(
                status_code=401,
                detail="The API key for this model was rejected. Update it in Settings.",
            )
        raise HTTPException(status_code=500, detail=f"Chain Error: {str(e)}")


@router.post("/agent/write", response_model=WriteResponse)
async def agent_write(
    intent: AgentIntent,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    try:
        requested_a1, actual_a1 = kernel.process_agent_intent(intent)
        return WriteResponse(
            status="Success" if requested_a1 == actual_a1 else "Collision Resolved",
            original_target=requested_a1,
            actual_target=actual_a1,
            message=f"Wrote data starting at {actual_a1}",
        )
    except Exception as e:
        return WriteResponse(
            status="Error",
            original_target=intent.target_start_a1,
            actual_target=intent.target_start_a1,
            message=str(e),
        )


@router.post("/agent/write/graph", response_model=WriteResponse)
async def agent_write_graph(
    req: NodeGraphRequest,
    k: GridOSKernel = Depends(current_kernel_dep),
):
    try:
        parser = IntentParser(agent_id=req.agent_id)
        graph = parser.parse(req.llm_response, prompt=req.prompt)
        is_valid, errors = validate_with_feedback(graph, Coordinator(kernel))
        if not is_valid:
            print(f"[graph] validation errors: {errors}")
            intents = parser.to_agent_intents(graph)
            if intents:
                requested_a1, actual_a1 = kernel.process_agent_intent(intents[0])
                return WriteResponse(
                    status="Fallback",
                    original_target=requested_a1,
                    actual_target=actual_a1,
                    message=f"Wrote via fallback at {actual_a1}",
                )
        nullified = graph.propagate_nulls()
        intents = parser.to_agent_intents(graph)
        if not intents:
            return WriteResponse(
                status="No-op",
                original_target="N/A",
                actual_target="N/A",
                message="Graph produced no write intents",
            )
        first_actual = None
        for intent in intents:
            requested_a1, actual_a1 = kernel.process_agent_intent(intent)
            if first_actual is None:
                first_actual = actual_a1
        audit_log = graph.to_audit_log()
        return WriteResponse(
            status="Success",
            original_target=intents[0].target_start_a1 if intents else "N/A",
            actual_target=first_actual or "N/A",
            message=f"Wrote {len(intents)} intents via graph",
        )
    except Exception as e:
        return WriteResponse(
            status="Error",
            original_target="N/A",
            actual_target="N/A",
            message=f"Node graph failed: {str(e)}",
        )


@router.post("/agent/execute-graph")
async def agent_execute_graph(
    request: Request,
    body: dict = Body(...),
    _user: Optional[AuthUser] = Depends(optional_user),
):
    k = _current_kernel.get()
    if k is None:
        k = _default_kernel

    graph_data = body.get("graph", body)
    nodes_data = graph_data.get("nodes", [])

    if not nodes_data:
        return {
            "success": False,
            "error": "No nodes provided in graph",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    try:
        graph = NodeGraph()
        for node_data in nodes_data:
            node_id = node_data.get("id", f"node_{len(graph.nodes)}")
            node_type_str = node_data.get("type", "QUERY")
            node_type = NodeType[node_type_str.upper()] if hasattr(NodeType, node_type_str.upper()) else NodeType.QUERY
            node = Node(
                id=node_id,
                node_type=node_type,
                interface=TypedInterface(inputs={}, outputs={}),
                inputs=node_data.get("inputs", {}),
                outputs={}
            )
            graph.add_node(node)

        coordinator = Coordinator(kernel=k)
        executor = Executor(formula_registry={})

        try:
            execution_order = coordinator.plan_execution(graph)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Graph validation failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        result = await executor.execute(execution_order)

        return {
            "success": True,
            "result": result,
            "executed_nodes": len(result.get("executed", [])),
            "failed_nodes": len(result.get("failed", [])),
            "skipped_nodes": len(result.get("skipped", [])),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

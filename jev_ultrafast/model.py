"""OpenAI-compatible model helpers for standalone Jev runs.

Codex's MCP integration can choose actions itself and call Jev's observed-action
tools. This module is for optional autonomous mode, using a local endpoint such
as CLIPRox. Only code-owned action IDs are accepted from the model.
"""

import json
import math
import os
import time

import httpx

from .questions import NEXT_ACTION, TARGET, TEXT_VALUE

CLIENT = httpx.Client(http2=True, timeout=25)


def post_json(url, key, body):
    for attempt in range(3):
        try:
            response = CLIENT.post(url, json=body, headers={"Authorization": f"Bearer {key}"})
        except httpx.HTTPError:
            raise RuntimeError("Model connection failed; no action executed.") from None
        if response.status_code in {429, 529, 503} and attempt < 2:
            time.sleep(0.5 * 2**attempt)
            continue
        if response.is_error:
            raise RuntimeError(f"Model provider returned HTTP {response.status_code}; no action executed.")
        return response.json()
    raise RuntimeError("Model unavailable")


def validate_choice(answer, ids):
    try:
        probabilities = answer["probabilities"]
        numbers = [*probabilities.values(), answer["confidence"]]
        valid = (
            answer["choice"] in ids
            and set(probabilities) == set(ids)
            and all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in numbers)
            and abs(sum(probabilities.values()) - 1) < 0.02
            and probabilities[answer["choice"]] >= max(probabilities.values()) - 1e-6
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Invalid model response; no action executed.")
    return answer


def action_space(actions):
    """One index per observed element; each operation has its own valid target choices."""
    elements, indices, targets, controls = [], {}, {}, {}
    operations = {"click": "CLICK", "fill": "TYPE_TEXT", "select": "SELECT"}
    for action in actions:
        kind = action["kind"]
        if kind not in operations:
            controls[action["id"].upper()] = action
            continue
        node = action["node"]
        if node not in indices:
            index = str(len(elements) + 1)
            indices[node] = index
            element = {k: action[k] for k in ("role", "value", "checked", "selected", "expanded") if k in action}
            element.update(index=index, label=action["label"].split(" → ")[0], operations=[])
            if kind == "select":
                element["value"] = action.get("current_value", "")
                element["options"] = []
            elements.append(element)
        index = indices[node]
        operation = operations[kind]
        group = targets.setdefault(operation, {})
        element = elements[int(index) - 1]
        if operation not in element["operations"]:
            element["operations"].append(operation)
        target = index
        if kind == "select":
            target = f"{index}:{len(element['options']) + 1}"
            element["options"].append({"index": target, "label": action["label"], "value": action["value"]})
        group[target] = action
    return elements, targets, controls


def choose(state, goal, history):
    elements, targets, controls = action_space(state["actions"])
    del elements
    actions_by_id = {action["id"]: action for group in targets.values() for action in group.values()}
    actions_by_id.update({action["id"]: action for action in controls.values()})
    candidates = {
        action_id: {
            "operation": action.get("kind", "control").upper(),
            "label": action.get("label", action_id),
            "current_value": action.get("current_value", action.get("value", "")),
            **{k: action[k] for k in ("role", "checked", "selected", "expanded") if k in action},
        }
        for action_id, action in actions_by_id.items()
    }
    candidates["DONE"] = {"operation": "DONE", "label": "Every requirement is visibly satisfied."}
    candidates["BLOCKED"] = {"operation": "BLOCKED", "label": "No supported operation can progress."}
    model = os.environ.get("JEVBROW_MODEL", "gemini-3.8-flash-high")
    body = {
        "model": model,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": NEXT_ACTION + "\n" + TARGET
                + '\nReturn only JSON with exactly these keys: {"choice":"<one offered ID>","confidence":0.0}.',
            },
            {
                "role": "user",
                "content": json.dumps({
                    "goal": goal,
                    "page": {k: state[k] for k in ("url", "title", "text")},
                    "recent_actions": [
                        {k: h.get(k) for k in ("action", "kind", "text", "page_changed")} for h in history[-10:]
                    ],
                    "available_actions": candidates,
                }),
            },
        ],
    }
    started = time.perf_counter()
    result = post_json(_model_endpoint(), _model_key(), body)
    try:
        answer = json.loads(result["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise ValueError("Model returned no valid action choice; no action executed.") from None
    if not isinstance(answer, dict) or set(answer) != {"choice", "confidence"}:
        raise ValueError("Model response must contain only choice and confidence; no action executed.")
    choice, confidence = answer["choice"], answer["confidence"]
    if (not isinstance(choice, str) or choice not in candidates or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise ValueError("Model selected an unavailable action; no action executed.")
    operation = candidates[choice]["operation"]
    target = choice if choice in actions_by_id else None
    return {
        "choice": choice,
        "operation": operation,
        "target": target,
        "confidence": confidence,
        "probabilities": {choice: 1.0},
        "operation_probabilities": {operation: 1.0},
        "target_probabilities": {target: 1.0} if target else {},
        "target_confidence": confidence if target else None,
        "raw_answers": answer,
        "model": result.get("model", model),
        "usage": result.get("usage", {}),
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "request": {"model": model, "goal": goal, "available_actions": candidates},
    }


def _model_base_url():
    return os.environ.get("JEVBROW_MODEL_BASE_URL", "http://127.0.0.1:8317/v1").rstrip("/")


def _model_endpoint():
    return _model_base_url() + "/chat/completions"


def _model_key():
    key = os.environ.get("JEVBROW_MODEL_API_KEY")
    if not key:
        raise ValueError("Autonomous mode needs JEVBROW_MODEL_API_KEY for the local model endpoint.")
    return key


def field_context(goal, action, page, history):
    return {
        "goal": goal,
        "field": {k: action.get(k) for k in ("label", "role", "value")},
        "page": {"title": page["title"], "text": page["text"][:6000]},
        "recent_actions": [{k: h.get(k) for k in ("action", "text")} for h in history[-6:]],
    }


def field_text(context):
    model = os.environ.get("JEVBROW_MODEL", "gemini-3.8-flash-high")
    started = time.perf_counter()
    result = post_json(
        _model_endpoint(),
        _model_key(),
        {
            "model": model,
            "max_tokens": 1024,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": TEXT_VALUE},
                {
                    "role": "user",
                    "content": json.dumps(context),
                },
            ],
        },
    )
    try:
        output = json.loads(result["choices"][0]["message"]["content"])
        value = output["text"]
        if set(output) != {"text"} or not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise ValueError()
    except (ValueError, KeyError, IndexError, TypeError):
        raise ValueError("Text helper returned no valid field value; nothing typed.") from None
    return value, {
        "model": model,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "usage": result.get("usage", {}),
    }

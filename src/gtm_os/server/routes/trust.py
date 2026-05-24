"""Trust scores + proposed experiments + simulation REST API (WS8C/8D/8E)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


# ---------- Trust scores (WS8C) ----------

@router.get("/trust-scores")
async def list_trust_scores(request: Request):
    gtm = request.app.state.gtm
    return {"trust_scores": gtm.store.list_trust_scores()}


@router.get("/trust-scores/{experiment_type}")
async def get_trust_score(experiment_type: str, request: Request):
    gtm = request.app.state.gtm
    score = gtm.store.get_trust_score(experiment_type)
    if not score:
        return {"trust_score": {"experiment_type": experiment_type, "score": 0.0}}
    return {"trust_score": score}


# ---------- Proposed experiments (WS8D) ----------

@router.get("/proposed-experiments")
async def list_proposed(request: Request, status: str | None = None):
    gtm = request.app.state.gtm
    return {"proposals": gtm.store.list_proposed_experiments(status=status)}


class ApproveProposalBody(BaseModel):
    action: str = "approve"  # "approve" or "reject"


@router.post("/proposed-experiments/{proposal_id}/review")
async def review_proposal(proposal_id: str, body: ApproveProposalBody, request: Request):
    gtm = request.app.state.gtm
    proposals = gtm.store.list_proposed_experiments()
    proposal = next((p for p in proposals if p["id"] == proposal_id), None)
    if not proposal:
        raise HTTPException(404, "proposal not found")

    if body.action == "approve":
        import json

        play_ids = proposal.get("play_ids", [])
        if isinstance(play_ids, str):
            play_ids = json.loads(play_ids)

        exp = gtm.runner.create(
            name=proposal["name"],
            hypothesis=proposal.get("hypothesis"),
            play_ids=play_ids,
        )
        gtm.store.update_proposed_experiment(proposal_id, "approved")
        return {"ok": True, "action": "approved", "experiment_id": exp.id}
    else:
        gtm.store.update_proposed_experiment(proposal_id, "rejected")
        return {"ok": True, "action": "rejected"}


# ---------- Simulation (WS8E) ----------

@router.post("/experiments/{experiment_id}/simulate")
async def simulate_experiment(experiment_id: str, request: Request):
    gtm = request.app.state.gtm
    exp = gtm.store.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(404, "experiment not found")

    from ...engine.simulation import predict_outcomes

    result = predict_outcomes(gtm.store, experiment_id)
    return {
        "ok": True,
        "predictions": [
            {
                "name": p.name,
                "predicted_value": p.predicted_value,
                "confidence_interval": [p.confidence_interval_low, p.confidence_interval_high],
                "based_on_experiments": p.based_on_experiments,
                "confidence_pct": p.confidence_pct,
            }
            for p in result.predictions
        ],
        "estimated_token_cost": result.estimated_token_cost,
        "estimated_dollar_cost": result.estimated_dollar_cost,
        "similar_experiments_found": result.similar_experiments_found,
        "message": result.message,
    }


# ---------- Feedback / approval with diff (WS8B) ----------

class ApproveWithFeedbackBody(BaseModel):
    original_content: str
    approved_content: str


@router.post("/experiments/{experiment_id}/approve")
async def approve_with_feedback(experiment_id: str, body: ApproveWithFeedbackBody, request: Request):
    gtm = request.app.state.gtm
    exp = gtm.store.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(404, "experiment not found")

    from ...engine.feedback import process_feedback

    result = await process_feedback(
        original=body.original_content,
        approved=body.approved_content,
        experiment_id=experiment_id,
        memory=gtm.memory,
        store=gtm.store,
    )

    # Resume experiment.
    gtm.runner.resume(experiment_id, target_phase="execute")

    return {
        "ok": True,
        "corrections_found": len(result.corrections),
        "memories_saved": result.memories_saved,
        "rules_promoted": result.rules_promoted,
        "phase": "execute",
    }

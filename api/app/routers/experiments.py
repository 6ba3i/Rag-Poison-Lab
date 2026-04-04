from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.app.services.orchestration_service import ExperimentOrchestrator, ExperimentRunOptions, resolve_optional_path
from common.schemas.api_types import ExperimentRunRequest, ExperimentRunResponse

router = APIRouter(tags=["experiments"])


@router.post("/experiments/run", response_model=ExperimentRunResponse)
def run_experiment(payload: ExperimentRunRequest) -> ExperimentRunResponse:
    orchestrator = ExperimentOrchestrator()
    try:
        result = orchestrator.run(
            options=ExperimentRunOptions(
                label=payload.label,
                mode=payload.mode,
                k=payload.k,
                user_id=payload.user_id,
                batch_size=payload.batch_size,
                run_profile=payload.run_profile,
                run_prepare=payload.run_prepare,
                run_index=payload.run_index,
                run_eval=payload.run_eval,
                run_report=payload.run_report,
                overwrite=payload.overwrite,
                dataset_dir=resolve_optional_path(payload.dataset_dir),
                output_dir=resolve_optional_path(payload.output_dir),
                es_url=payload.es_url,
                attack_config=resolve_optional_path(payload.attack_config),
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ExperimentRunResponse.model_validate(result)

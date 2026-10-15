from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from slack_sdk.errors import SlackApiError

from app.jobs import JobManager
from app.services.realtime_service import RealtimeService

router = APIRouter()


class BackfillRequest(BaseModel):
    channel_ids: list[str] = Field(min_length=1)
    page_size: int = Field(default=200, ge=1, le=1000)


def get_jobs(request: Request) -> JobManager:
    return request.app.state.jobs


Jobs = Annotated[JobManager, Depends(get_jobs)]


@router.post("/backfill", status_code=202)
def backfill(body: BackfillRequest, jobs: Jobs):
    started = jobs.start_backfill(body.channel_ids, body.page_size)
    skipped = [c for c in dict.fromkeys(body.channel_ids) if c not in started]
    return {"started": started, "already_running": skipped}


@router.post("/pause")
def pause(jobs: Jobs):
    jobs.pause()
    return jobs.status()


@router.post("/resume")
def resume(jobs: Jobs):
    jobs.resume()
    return jobs.status()


@router.get("/status")
def status(jobs: Jobs, realtime: Realtime):
    return {**jobs.status(), "realtime": realtime.status()}


def get_realtime(request: Request) -> RealtimeService:
    return request.app.state.realtime


Realtime = Annotated[RealtimeService, Depends(get_realtime)]


@router.post("/realtime/start", tags=["realtime"])
def realtime_start(realtime: Realtime):
    if not realtime.configured:
        raise HTTPException(503, "SLACK_APP_TOKEN is not set")
    try:
        started = realtime.start()
    except SlackApiError as e:
        raise HTTPException(502, f"could not open Socket Mode: {e}") from e
    return {"started": started, **realtime.status()}


@router.post("/realtime/stop", tags=["realtime"])
def realtime_stop(realtime: Realtime):
    stopped = realtime.stop()
    return {"stopped": stopped, **realtime.status()}


@router.post("/metadata/sync", tags=["metadata"])
def metadata_sync(jobs: Jobs):
    try:
        return jobs.sync_metadata()
    except SlackApiError as e:
        raise HTTPException(502, f"slack error: {e.response.get('error')}") from e

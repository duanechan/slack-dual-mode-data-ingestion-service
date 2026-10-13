from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.jobs import JobManager

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
def status(jobs: Jobs):
    return jobs.status()

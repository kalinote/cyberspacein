from fastapi import APIRouter, Depends

from app.curd.action import get_components_by_project_id, get_components_project_by_name
from app.schemas.action import BaseComponent
from app.schemas.general import PageParams, PageResponse

router = APIRouter(
    prefix="/action",
    tags=["action"],
)

@router.get("/nodes")
async def get_actions():
    return {"message": "Hello, World!"}

@router.get("/resource_management/base_components", response_model=PageResponse[BaseComponent])
async def get_base_components(
    params: PageParams = Depends()
):
    project_id = await get_components_project_by_name("csi_base_components")
    components = await get_components_by_project_id(project_id, params.page, params.page_size)

    results = []
    for component in components:
        results.append(BaseComponent(
            id=component["_id"],
            name=component["name"],
            description=component["description"],
            status=component["stat"]["last_task"].get("status", "unknown"),
            last_run_at=component["stat"]["last_task"].get("create_ts", None),
            total_runs=component["stat"]["tasks"],
            average_runtime=component["stat"]["average_total_duration"],
        ))

    return PageResponse.create(results, len(components), params.page, params.page_size)

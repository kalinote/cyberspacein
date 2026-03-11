import random
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from beanie.operators import Set

from app.models.action.accounts import (
    AccountModel,
    CredentialsModel,
    EnvironmentModel,
    RateLimitModel,
    SchedulerModel,
)
from app.models.platform.platform import PlatformModel
from app.schemas.action.accounts import (
    AccountCreateRequest,
    AccountUpdateRequest,
    AccountResponse,
    CredentialsSchema,
    EnvironmentSchema,
    RateLimitSchema,
    SchedulerSchema,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.utils.id_lib import generate_id

router = APIRouter(prefix="/accounts", tags=["账号管理"])


def _doc_to_response(doc: AccountModel) -> AccountResponse:
    return AccountResponse(
        id=doc.id,
        platform_id=doc.platform_id,
        account_name=doc.account_name,
        is_deleted=doc.is_deleted,
        credentials=CredentialsSchema.model_validate(doc.credentials.model_dump()),
        scheduler=SchedulerSchema.model_validate(doc.scheduler.model_dump()),
        rate_limit=RateLimitSchema.model_validate(doc.rate_limit.model_dump()),
        environment=EnvironmentSchema.model_validate(doc.environment.model_dump()),
        status=doc.status,
        status_reason=doc.status_reason,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("", response_model=ApiResponseSchema[AccountResponse], summary="创建账号")
async def create_account(data: AccountCreateRequest):
    platform = await PlatformModel.find_one({"_id": data.platform_id})
    if not platform:
        return ApiResponseSchema.error(code=404, message=f"平台不存在，ID: {data.platform_id}")

    raw = data.platform_id + data.account_name + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
    account_id = generate_id(raw)
    existing = await AccountModel.find_one({"_id": account_id})
    if existing:
        return ApiResponseSchema.error(code=400, message=f"账号已存在，ID: {account_id}")

    credentials = CredentialsModel(**(data.credentials.model_dump() if data.credentials else {}))
    scheduler = SchedulerModel(**(data.scheduler.model_dump() if data.scheduler else {}))
    rate_limit = RateLimitModel(**(data.rate_limit.model_dump() if data.rate_limit else {}))
    environment = EnvironmentModel(**(data.environment.model_dump() if data.environment else {}))

    account = AccountModel(
        id=account_id,
        platform_id=data.platform_id,
        account_name=data.account_name,
        credentials=credentials,
        scheduler=scheduler,
        rate_limit=rate_limit,
        environment=environment,
    )
    await account.insert()
    return ApiResponseSchema.success(data=_doc_to_response(account))


@router.get("/list", response_model=PageResponseSchema[AccountResponse], summary="获取账号列表")
async def get_account_list(
    params: PageParamsSchema = Depends(),
    platform_id: str | None = Query(default=None, description="按平台ID筛选"),
):
    query_filters: dict = {"is_deleted": False}
    if platform_id is not None:
        query_filters["platform_id"] = platform_id
    query = AccountModel.find(query_filters)
    total = await query.count()
    items = await query.skip((params.page - 1) * params.page_size).limit(params.page_size).to_list()
    results = [_doc_to_response(doc) for doc in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{account_id}", response_model=ApiResponseSchema[AccountResponse], summary="获取账号详情")
async def get_account_detail(account_id: str):
    doc = await AccountModel.find_one({"_id": account_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"账号不存在或已删除，ID: {account_id}")
    return ApiResponseSchema.success(data=_doc_to_response(doc))


@router.patch("/{account_id}", response_model=ApiResponseSchema[AccountResponse], summary="更新账号")
async def update_account(account_id: str, data: AccountUpdateRequest):
    doc = await AccountModel.find_one({"_id": account_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"账号不存在或已删除，ID: {account_id}")
    update_data = data.model_dump(exclude_unset=True)
    if "credentials" in update_data and update_data["credentials"] is not None:
        update_data["credentials"] = CredentialsModel(**update_data["credentials"])
    elif "credentials" in update_data:
        del update_data["credentials"]
    if "scheduler" in update_data and update_data["scheduler"] is not None:
        update_data["scheduler"] = SchedulerModel(**update_data["scheduler"])
    elif "scheduler" in update_data:
        del update_data["scheduler"]
    if "rate_limit" in update_data and update_data["rate_limit"] is not None:
        update_data["rate_limit"] = RateLimitModel(**update_data["rate_limit"])
    elif "rate_limit" in update_data:
        del update_data["rate_limit"]
    if "environment" in update_data and update_data["environment"] is not None:
        update_data["environment"] = EnvironmentModel(**update_data["environment"])
    elif "environment" in update_data:
        del update_data["environment"]
    update_data["updated_at"] = datetime.now()
    await doc.update({"$set": update_data})
    updated = await AccountModel.get(account_id)
    return ApiResponseSchema.success(data=_doc_to_response(updated))


@router.delete("/{account_id}", response_model=ApiResponseSchema[None], summary="删除账号(软删除)")
async def delete_account(account_id: str):
    doc = await AccountModel.find_one({"_id": account_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"账号不存在或已删除，ID: {account_id}")
    await doc.update(Set({
        AccountModel.is_deleted: True,
        AccountModel.updated_at: datetime.now(),
    }))
    return ApiResponseSchema.success()

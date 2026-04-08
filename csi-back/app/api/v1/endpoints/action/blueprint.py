import logging
from fastapi import APIRouter, Depends
from app.models.action.blueprint import (
    ActionBlueprintModel,
    PositionModel,
    NodeDataModel,
    GraphNodeModel,
    GraphEdgeModel,
    ViewportModel,
    GraphModel,
)
from app.schemas.action.blueprint import (
    ActionBlueprintSchema,
    ActionBlueprintBaseInfoResponse,
    ActionBlueprintDetailResponseSchema,
    TemplateSpecSchema,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict
from app.utils.workflow import count_workflow_paths, graph_model2schemas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blueprint", tags=["行动蓝图"])


@router.post("", response_model=ApiResponseSchema[ActionBlueprintDetailResponseSchema], summary="创建蓝图")
async def create_blueprint(data: ActionBlueprintSchema):
    if data.is_template:
        param_names = [p.name for p in data.template.params]
        if len(param_names) != len(set(param_names)):
            return ApiResponseSchema.error(code=240001, message="参数名称必须唯一")

        for node_bindings in data.template.bindings.values():
            for binding_name, binding_param in node_bindings.items():
                if binding_param not in param_names:
                    return ApiResponseSchema.error(
                        code=240001,
                        message=f"绑定引用的参数 '{binding_param}' 不存在"
                    )

    blueprint_id = generate_id(data.name + data.version + str(len(data.graph.nodes)) + str(len(data.graph.edges)))

    existing_blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if existing_blueprint:
        return ApiResponseSchema.error(code=240901, message=f"蓝图已存在，ID: {blueprint_id}")

    nodes_models = []
    for node in data.graph.nodes:
        node_data_model = NodeDataModel(
            definition_id=node.data.definition_id,
            version=node.data.version,
            form_data=pack_dict(node.data.form_data)
        )

        position_model = PositionModel(
            x=node.position.x,
            y=node.position.y
        )

        node_model = GraphNodeModel(
            id=node.id,
            type=node.type,
            position=position_model,
            data=node_data_model
        )
        nodes_models.append(node_model)

    edges_models = []
    for edge in data.graph.edges:
        edge_model = GraphEdgeModel(
            id=edge.id,
            source=edge.source,
            sourceHandle=edge.sourceHandle,
            target=edge.target,
            targetHandle=edge.targetHandle
        )
        edges_models.append(edge_model)

    viewport_model = ViewportModel(
        x=data.graph.viewport.x,
        y=data.graph.viewport.y,
        zoom=data.graph.viewport.zoom
    )

    graph_model = GraphModel(
        nodes=nodes_models,
        edges=edges_models,
        viewport=viewport_model
    )

    blueprint_model = ActionBlueprintModel(
        id=blueprint_id,
        name=data.name,
        version=data.version,
        description=data.description,
        target=data.target,
        implementation_period=data.implementation_period,
        resource=data.resource,
        graph=graph_model,
        is_template=data.is_template,
        template=data.template.model_dump() if data.template else None
    )

    await blueprint_model.insert()
    logger.info(f"成功创建蓝图: {blueprint_id}")

    await ActionInstanceService._clear_cache("blueprint", blueprint_id)

    response_data = ActionBlueprintDetailResponseSchema(
        id=blueprint_id,
        name=data.name,
        version=data.version,
        description=data.description,
        target=data.target,
        implementation_period=data.implementation_period,
        resource=data.resource,
        graph=data.graph,
        created_at=blueprint_model.created_at,
        updated_at=blueprint_model.updated_at,
        is_template=blueprint_model.is_template,
        template=data.template
    )

    return ApiResponseSchema.success(data=response_data)


@router.get("/list", response_model=PageResponseSchema[ActionBlueprintBaseInfoResponse], summary="获取蓝图列表")
async def get_blueprints(
    params: PageParamsSchema = Depends()
):
    skip = (params.page - 1) * params.page_size

    total = await ActionBlueprintModel.find_all().count()
    blueprints = await ActionBlueprintModel.find_all().skip(skip).limit(params.page_size).to_list()

    results = []
    for blueprint in blueprints:
        steps = len(blueprint.graph.nodes)
        branches = count_workflow_paths(blueprint)

        results.append(ActionBlueprintBaseInfoResponse(
            id=blueprint.id,
            name=blueprint.name,
            version=blueprint.version,
            description=blueprint.description,
            target=blueprint.target,
            implementation_period=blueprint.implementation_period,
            created_at=blueprint.created_at,
            updated_at=blueprint.updated_at,
            steps=steps,
            branches=branches,
            is_template=blueprint.is_template,
        ))

    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{blueprint_id}", response_model=ApiResponseSchema[ActionBlueprintDetailResponseSchema], summary="获取蓝图详情")
async def get_blueprint(blueprint_id: str):
    blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if not blueprint:
        return ApiResponseSchema.error(code=240411, message=f"蓝图不存在，ID: {blueprint_id}")

    graph = graph_model2schemas(blueprint.graph)

    response_data = ActionBlueprintDetailResponseSchema(
        id=blueprint.id,
        name=blueprint.name,
        version=blueprint.version,
        description=blueprint.description,
        target=blueprint.target,
        implementation_period=blueprint.implementation_period,
        resource=blueprint.resource,
        graph=graph,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        is_template=blueprint.is_template,
        template=TemplateSpecSchema(**blueprint.template) if blueprint.template else None
    )

    return ApiResponseSchema.success(data=response_data)

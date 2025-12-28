from collections import defaultdict

from app.models.action.blueprint import ActionBlueprintModel, GraphNodeModel, GraphModel
from app.schemas.action.blueprint import Graph, GraphNode, GraphEdge, Position, NodeData, Viewport
from app.utils.dict_helper import unpack_dict


def find_start_nodes(action_blueprint: ActionBlueprintModel) -> list[GraphNodeModel]:
    """查找起始节点（入度为0的节点）"""
    nodes = action_blueprint.graph.nodes
    edges = action_blueprint.graph.edges

    adj_list = defaultdict(list)
    in_degree = defaultdict(int)

    all_node_ids = set()
    for node in nodes:
        all_node_ids.add(node.id)
        in_degree[node.id] = 0

    for edge in edges:
        source = edge.source
        target = edge.target

        adj_list[source].append(target)
        in_degree[target] += 1

    start_nodes = [
        node for node in nodes if in_degree[node.id] == 0]

    return start_nodes


def count_workflow_paths(action_blueprint: ActionBlueprintModel) -> int:
    """计算工作流路径数量"""
    nodes = action_blueprint.graph.nodes
    edges = action_blueprint.graph.edges

    adj_list = defaultdict(list)
    in_degree = defaultdict(int)

    all_node_ids = set()
    for node in nodes:
        all_node_ids.add(node.id)
        in_degree[node.id] = 0

    for edge in edges:
        source = edge.source
        target = edge.target

        adj_list[source].append(target)
        in_degree[target] += 1

    start_nodes = find_start_nodes(action_blueprint)

    memo: dict[str, int] = {}

    def get_paths_from(node_id: str) -> int:
        if node_id in memo:
            return memo[node_id]

        neighbors = adj_list[node_id]

        if not neighbors:
            return 1

        total_paths = 0
        for neighbor in neighbors:
            total_paths += get_paths_from(neighbor)

        memo[node_id] = total_paths
        return total_paths

    total_count = 0
    for start_node in start_nodes:
        path_count = get_paths_from(start_node.id)
        total_count += path_count

    return total_count


def graph_model2schemas(graph_model: GraphModel) -> Graph:
    """将 GraphModel 转换为 Graph schema"""
    nodes = []
    for node_model in graph_model.nodes:
        form_data = unpack_dict(node_model.data.form_data) or {}
        node_data = NodeData(
            definition_id=node_model.data.definition_id,
            version=node_model.data.version,
            form_data=form_data
        )
        
        position = Position(
            x=node_model.position.x,
            y=node_model.position.y
        )
        
        node = GraphNode(
            id=node_model.id,
            type=node_model.type,
            position=position,
            data=node_data
        )
        nodes.append(node)
    
    edges = []
    for edge_model in graph_model.edges:
        edge = GraphEdge(
            id=edge_model.id,
            source=edge_model.source,
            sourceHandle=edge_model.sourceHandle,
            target=edge_model.target,
            targetHandle=edge_model.targetHandle
        )
        edges.append(edge)
    
    viewport = Viewport(
        x=graph_model.viewport.x,
        y=graph_model.viewport.y,
        zoom=graph_model.viewport.zoom
    )
    
    graph = Graph(
        nodes=nodes,
        edges=edges,
        viewport=viewport
    )
    
    return graph
from collections import defaultdict


def count_workflow_paths(json_data: dict) -> int:
    """计算工作流路径数量"""
    nodes = json_data.get("graph", {}).get("nodes", [])
    edges = json_data.get("graph", {}).get("edges", [])

    adj_list = defaultdict(list)
    in_degree = defaultdict(int)

    all_node_ids = set()
    for node in nodes:
        all_node_ids.add(node['id'])
        in_degree[node['id']] = 0

    for edge in edges:
        source = edge['source']
        target = edge['target']

        adj_list[source].append(target)
        in_degree[target] += 1

    start_nodes = [
        node_id for node_id in all_node_ids if in_degree[node_id] == 0]

    memo = {}

    def get_paths_from(node_id):
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
        path_count = get_paths_from(start_node)
        total_count += path_count

    return total_count
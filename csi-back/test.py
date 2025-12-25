import json
from collections import defaultdict


def count_workflow_paths(json_data):
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

    print(f"检测到 {len(start_nodes)} 个起点: {start_nodes}")

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
        print(f"起点 [{start_node}] 贡献了 {path_count} 条路径")
        total_count += path_count

    return total_count


json_str = """
{
  "name": "111",
  "version": "1.0.0",
  "description": "222",
  "target": "333",
  "implementation_period": 3600,
  "resource": {},
  "graph": {
    "nodes": [
      {
        "id": "node-1766678963606",
        "type": "crawler",
        "position": {
          "x": 807,
          "y": 365.5
        },
        "data": {
          "definition_id": "4215c71cb06428eaed6ea8c0e2bb8c51",
          "version": "1.0.0",
          "form_data": {
            "page": 0
          }
        }
      },
      {
        "id": "node-1766678965371",
        "type": "construct",
        "position": {
          "x": 405.4107594190075,
          "y": 175.87428456971077
        },
        "data": {
          "definition_id": "2d11020cbfe3d038f4cfaeaf72e0a38e",
          "version": "1.0.0",
          "form_data": {
            "keywords": []
          }
        }
      },
      {
        "id": "node-1766678969012",
        "type": "construct",
        "position": {
          "x": 392.21568031127856,
          "y": 356.64686834559734
        },
        "data": {
          "definition_id": "ffcc5955ff1164f775155ffee655e8f3",
          "version": "1.0.0",
          "form_data": {
            "platforms": []
          }
        }
      },
      {
        "id": "node-1766678972101",
        "type": "construct",
        "position": {
          "x": 608.3222932163408,
          "y": 584.4165982192468
        },
        "data": {
          "definition_id": "febab00d7dd21735e240eaff5e167f01",
          "version": "1.0.0",
          "form_data": {
            "conditions": []
          }
        }
      },
      {
        "id": "node-1766678974314",
        "type": "middleware",
        "position": {
          "x": 1265.1591594921767,
          "y": 387.520058521808
        },
        "data": {
          "definition_id": "dcec64d3ead98984d65d62ed30899b6c",
          "version": "1.0.0",
          "form_data": {
            "target_name": "",
            "batch_size": 0,
            "storage_filter": false
          }
        }
      },
      {
        "id": "node-1766678979739",
        "type": "storage",
        "position": {
          "x": 1258.1920013652712,
          "y": 649.7402920615631
        },
        "data": {
          "definition_id": "6a215518fd6a7389e190de97be741176",
          "version": "1.0.0",
          "form_data": {
            "target_name": "",
            "batch_size": 0,
            "storage_filter": false
          }
        }
      },
      {
        "id": "node-1766678989518",
        "type": "storage",
        "position": {
          "x": 1759.2643878560407,
          "y": 615.5236270882579
        },
        "data": {
          "definition_id": "6a215518fd6a7389e190de97be741176",
          "version": "1.0.0",
          "form_data": {
            "target_name": "",
            "batch_size": 0,
            "storage_filter": false
          }
        }
      },
      {
        "id": "node-1766678995282",
        "type": "middleware",
        "position": {
          "x": 1763.2643878560407,
          "y": 364.5236270882578
        },
        "data": {
          "definition_id": "dcec64d3ead98984d65d62ed30899b6c",
          "version": "1.0.0",
          "form_data": {
            "target_name": "",
            "batch_size": 0,
            "storage_filter": false
          }
        }
      }
    ],
    "edges": [
      {
        "id": "vueflow__edge-node-17666789653713045760640953fbbdbc1484b3beb52f1-node-17666789636063d35d9a35af9b9dda3633be10783001d",
        "source": "node-1766678965371",
        "sourceHandle": "3045760640953fbbdbc1484b3beb52f1",
        "target": "node-1766678963606",
        "targetHandle": "3d35d9a35af9b9dda3633be10783001d"
      },
      {
        "id": "vueflow__edge-node-1766678969012c5c840162ee803f90173ef3880dba422-node-1766678963606f79b7a7211a9c06ed8e31badc8a723be",
        "source": "node-1766678969012",
        "sourceHandle": "c5c840162ee803f90173ef3880dba422",
        "target": "node-1766678963606",
        "targetHandle": "f79b7a7211a9c06ed8e31badc8a723be"
      },
      {
        "id": "vueflow__edge-node-176667897210177dbc2e3da30ccc136cc68207e8591b4-node-17666789743147b83a20fc8001aac74d0ca2af4e43b43",
        "source": "node-1766678972101",
        "sourceHandle": "77dbc2e3da30ccc136cc68207e8591b4",
        "target": "node-1766678974314",
        "targetHandle": "7b83a20fc8001aac74d0ca2af4e43b43"
      },
      {
        "id": "vueflow__edge-node-1766678963606c587f1f846f4615979d19f0aca04b8b4-node-1766678974314392a19e03d09138ead4c948a6404aaac",
        "source": "node-1766678963606",
        "sourceHandle": "c587f1f846f4615979d19f0aca04b8b4",
        "target": "node-1766678974314",
        "targetHandle": "392a19e03d09138ead4c948a6404aaac"
      },
      {
        "id": "vueflow__edge-node-1766678963606c587f1f846f4615979d19f0aca04b8b4-node-1766678979739392a19e03d09138ead4c948a6404aaac",
        "source": "node-1766678963606",
        "sourceHandle": "c587f1f846f4615979d19f0aca04b8b4",
        "target": "node-1766678979739",
        "targetHandle": "392a19e03d09138ead4c948a6404aaac"
      },
      {
        "id": "vueflow__edge-node-176667897210177dbc2e3da30ccc136cc68207e8591b4-node-17666789797397b83a20fc8001aac74d0ca2af4e43b43",
        "source": "node-1766678972101",
        "sourceHandle": "77dbc2e3da30ccc136cc68207e8591b4",
        "target": "node-1766678979739",
        "targetHandle": "7b83a20fc8001aac74d0ca2af4e43b43"
      },
      {
        "id": "vueflow__edge-node-1766678974314ab3affcf0586759f43f049bdb32d1124-node-1766678989518392a19e03d09138ead4c948a6404aaac",
        "source": "node-1766678974314",
        "sourceHandle": "ab3affcf0586759f43f049bdb32d1124",
        "target": "node-1766678989518",
        "targetHandle": "392a19e03d09138ead4c948a6404aaac"
      },
      {
        "id": "vueflow__edge-node-1766678974314ab3affcf0586759f43f049bdb32d1124-node-1766678995282392a19e03d09138ead4c948a6404aaac",
        "source": "node-1766678974314",
        "sourceHandle": "ab3affcf0586759f43f049bdb32d1124",
        "target": "node-1766678995282",
        "targetHandle": "392a19e03d09138ead4c948a6404aaac"
      }
    ],
    "viewport": {
      "x": -220.05617576560962,
      "y": 42.63440535948018,
      "zoom": 0.870550563296124
    }
  }
}
"""

data = json.loads(json_str)
total_paths = count_workflow_paths(data)

print("-" * 30)
print(f"最终计算结果：总共有 {total_paths} 种走法")

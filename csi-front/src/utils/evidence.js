export const NODE_KINDS = {
  entity: {
    label: '实体引用',
    icon: 'mdi:file-document-outline',
    color: '#2563eb'
  },
  note: {
    label: '自定义节点',
    icon: 'mdi:lightbulb-outline',
    color: '#d97706'
  },
  collection: {
    label: '固定集合',
    icon: 'mdi:folder-multiple-outline',
    color: '#0d9488'
  },
  versions: {
    label: '动态版本',
    icon: 'mdi:history',
    color: '#7c3aed'
  },
  chain: {
    label: '子链引用',
    icon: 'mdi:graph-outline',
    color: '#4f46e5'
  }
};
export const CHAIN_STATUS = {
  draft: '草稿',
  active: '分析中',
  archived: '已归档'
};
export const RELATION_STATUS = {
  pending: '待核实',
  confirmed: '人工确认',
  disputed: '有争议'
};
export const EVIDENCE_TEMPLATES = [{
  id: 'blank',
  name: '自由构建',
  icon: 'mdi:vector-polyline',
  description: '自行定义分析目的、节点与关系。',
  labels: [],
  relations: ['关联', '支持', '反驳', '补充', '引用', '先于']
}, {
  id: 'proof',
  name: '证明与反证',
  icon: 'mdi:check-decagram-outline',
  description: '围绕待验证判断，组织支持材料与反证。',
  labels: ['支持材料', '待验证判断', '反证与疑点'],
  relations: ['支持', '反驳', '补充', '引用', '关联']
}, {
  id: 'expansion',
  name: '信息扩展',
  icon: 'mdi:source-branch',
  description: '从一个线索出发，补充背景、关联与影响。',
  labels: ['核心线索', '相关背景', '外部影响'],
  relations: ['补充', '关联', '引用', '影响']
}, {
  id: 'trace',
  name: '事件溯源',
  icon: 'mdi:timeline-clock-outline',
  description: '沿时间梳理事件变化，分别记录顺序与因果。',
  labels: ['事件起点', '后续变化', '当前状态'],
  relations: ['先于', '演变为', '导致', '补充', '引用']
}];
export function evidenceId() {
  // 兼容局域网 HTTP 环境中不可用的 randomUUID。
  return globalThis.crypto?.randomUUID?.() || `n-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
export function makeEvidenceNode(kind, options = {}) {
  return {
    id: evidenceId(),
    kind,
    label: NODE_KINDS[kind].label,
    description: '',
    attributes: {},
    position: {
      x: 80,
      y: 80
    },
    entity: null,
    members: [],
    version_source: null,
    chain_id: null,
    ...options
  };
}
export function makeEvidenceGraph(templateId = 'blank', title = '未命名证据链') {
  const template = EVIDENCE_TEMPLATES.find(item => item.id === templateId) || EVIDENCE_TEMPLATES[0];
  const nodes = template.labels.map((label, index) => makeEvidenceNode('note', {
    label,
    position: {
      x: 80 + index * 340,
      y: 160
    }
  }));
  const edges = template.id === 'proof' ? [[0, 1, '支持'], [2, 1, '反驳']] : template.id === 'trace' ? [[0, 1, '先于'], [1, 2, '先于']] : template.id === 'expansion' ? [[1, 0, '补充'], [0, 2, '关联']] : [];
  return {
    title,
    description: '',
    purpose: '',
    template: template.id,
    status: 'draft',
    tags: [],
    relation_types: [...template.relations],
    nodes,
    edges: edges.map(([source, target, label]) => ({
      id: evidenceId(),
      source: nodes[source].id,
      target: nodes[target].id,
      label,
      directed: true,
      description: '',
      status: 'pending',
      anchors: []
    }))
  };
}
export function graphPayload(graph) {
  return Object.fromEntries(['title', 'description', 'purpose', 'template', 'status', 'tags', 'relation_types', 'nodes', 'edges'].map(key => [key, graph[key]]));
}
export function entityDetailPath(entity) {
  return `/details/${entity.entity_type}/${encodeURIComponent(entity.uuid)}`;
}
export function plainEntityTitle(value) {
  return String(value || '无标题').replace(/<[^>]*>/g, '').slice(0, 300);
}
export function memberPath(parent, entity) {
  return `${parent}/@${entity.entity_type}:${entity.uuid}`;
}
export function projectEvidenceGraph(graph, resolved = {}, expanded = new Set()) {
  const nodes = [];
  const rawEdges = [];
  const visit = (current, prefix = '', offset = {
    x: 0,
    y: 0
  }, depth = 0) => {
    if (depth > 32) return;
    for (const node of current.nodes) {
      const path = prefix + node.id;
      const position = {
        x: offset.x + node.position.x,
        y: offset.y + node.position.y
      };
      nodes.push({
        id: path,
        type: 'evidence',
        position,
        draggable: !prefix,
        data: {
          node,
          path,
          inherited: Boolean(prefix),
          resolved: resolved[path],
          expanded: expanded.has(path)
        }
      });
      const content = resolved[path];
      if (!expanded.has(path) || !content) continue;
      if (node.kind === 'chain' && content.chain) {
        visit(content.chain, `${path}/`, {
          x: position.x + 350,
          y: position.y + 160
        }, depth + 1);
      } else if (node.kind === 'collection' || node.kind === 'versions') {
        for (const [index, entity] of (content.items || []).entries()) {
          const childPath = memberPath(path, entity);
          const child = makeEvidenceNode('entity', {
            id: childPath,
            label: plainEntityTitle(entity.title),
            entity: {
              entity_type: entity.entity_type,
              uuid: entity.uuid
            }
          });
          nodes.push({
            id: childPath,
            type: 'evidence',
            position: {
              x: position.x + 350,
              y: position.y + index * 160
            },
            draggable: false,
            data: {
              node: child,
              path: childPath,
              inherited: true,
              resolved: resolved[childPath] || {
                items: [entity],
                resolved_at: content.resolved_at
              }
            }
          });
          rawEdges.push({
            id: `member:${childPath}`,
            source: path,
            target: childPath,
            label: '包含',
            selectable: false,
            style: {
              stroke: '#cbd5e1',
              strokeDasharray: '4 4'
            },
            data: {
              containment: true
            }
          });
        }
      }
    }
    for (const edge of current.edges) {
      rawEdges.push({
        id: prefix + edge.id,
        source: prefix + edge.source,
        target: prefix + edge.target,
        label: edge.label,
        markerEnd: edge.directed ? {
          type: 'arrowclosed',
          color: edge.status === 'disputed' ? '#e11d48' : '#64748b'
        } : undefined,
        style: {
          stroke: edge.status === 'disputed' ? '#e11d48' : '#64748b',
          strokeWidth: 1.8,
          strokeDasharray: edge.status === 'pending' ? '5 4' : undefined
        },
        data: {
          edge,
          inherited: Boolean(prefix),
          ownerPath: prefix
        }
      });
    }
  };
  visit(graph);
  const ids = new Set(nodes.map(node => node.id));
  const nearest = endpoint => {
    let current = endpoint;
    while (current && !ids.has(current)) current = current.includes('/') ? current.slice(0, current.lastIndexOf('/')) : '';
    return current;
  };
  const edges = rawEdges.flatMap(edge => {
    const source = nearest(edge.source);
    const target = nearest(edge.target);
    if (!source || !target) return [];
    const folded = source !== edge.source || target !== edge.target;
    const missing = [edge.source, edge.target].some(endpoint => {
      const parts = endpoint.split('/');
      for (let i = 1; i < parts.length; i++) {
        const parent = parts.slice(0, i).join('/');
        const content = resolved[parent];
        if (content?.chain && !content.chain.nodes.some(node => node.id === parts[i])) return true;
        if (content?.items && content.total <= content.items.length && parts[i].startsWith('@') && !content.items.some(item => `@${item.entity_type}:${item.uuid}` === parts[i])) return true;
      }
      return false;
    });
    return [{
      ...edge,
      source,
      target,
      type: 'smoothstep',
      label: `${edge.label}${missing ? ' · 引用失效' : folded ? ' · 内部节点' : ''}`,
      data: {
        ...edge.data,
        folded,
        missing
      }
    }];
  });
  return {
    nodes,
    edges
  };
}

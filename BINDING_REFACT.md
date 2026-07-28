# 蓝图 IO 绑定系统重构方案

## 1. 文档信息

- 文档状态：已实施并持续维护
- 适用范围：行动蓝图编辑、校验、发布、封装运行和历史数据兼容
- 关联方案：`COMPONENTS_REFACT_PLAN.md`
- 核心对象：蓝图输入节点、蓝图输出节点、普通数据 Handle、虚拟绑定 Handle、`boundary_binding`

本文档定义蓝图 IO 节点与普通节点之间“绑定替换”关系的最终语义、前后端契约、交互方案、迁移策略和验收标准。本文档中的“绑定”不等同于普通数据连线，也不等同于直接暴露普通节点端口。

本文档是 `COMPONENTS_REFACT_PLAN.md` 中边界绑定章节的细化和后续修订。两份文档在中间节点绑定、Handle 交互或校验规则上存在冲突时，以本文档为准；组件类型、Revision、执行计划等非绑定领域仍以原方案为准。

---

## 2. 背景

当前行动系统已经具备以下能力：

1. 蓝图输入、蓝图输出作为后端原生节点存在于设计图中。
2. 未绑定 IO 节点可通过普通数据 Handle 与其他节点连接。
3. IO 节点可拖动到非 IO 节点本体上，选择目标端口并建立 `boundary_binding`。
4. 独立运行时跳过 IO 节点，保留被绑定目标节点。
5. 封装运行时保留 IO 节点，跳过被绑定目标节点，并重写目标节点周围的数据边。
6. 输入 IO 和输出 IO 使用淡蓝色、淡紫色背景。
7. 被绑定目标节点已经能显示对应颜色的边框。
8. 拖动 IO 节点经过可绑定目标时已经具有候选高亮。
9. IO 节点和其他节点已经复用 `GenericNode`、`InputRenderer` 等通用 UI 组件。

当前实现仍存在以下问题：

1. 绑定关系主要依赖节点贴边、尾线和目标边框展示，关系表达不够明确。
2. 绑定只能通过拖动 IO 节点到目标节点本体触发，缺少精确的手动连接入口。
3. 任何具有兼容端口的非 IO 节点都可以被绑定，中间节点也不例外。
4. 同一目标节点可以同时绑定输入 IO 和输出 IO。
5. 编译器把绑定解释为“替换整个目标节点”，中间节点绑定可能拆断原图。
6. 编译器只禁止多个同方向 IO 重复替换同一个端口，不禁止同一节点上的输入、输出混合绑定。
7. 编译器不校验替换后公开输入、公开输出是否仍有有效数据路径。
8. 已绑定 IO 节点仍可能保留普通数据边，导致同一个 IO 同时具有“数据节点”和“替换节点”两种模式。
9. 前端展示状态依赖临时字段，尚未形成统一的派生状态模型。
10. Vue Flow 的 Handle 具有 `source`、`target` 方向，直接增加一个普通 Handle 无法同时自然承担两种绑定方向。

---

## 3. 重构目标

### 3.1 功能目标

1. 每个符合条件的非 IO 节点只展示一个统一的绑定 Handle。
2. 该绑定 Handle 可绑定多个 IO 节点，不按输入、输出拆成两个可见接口。
3. 绑定 Handle 不传输数据，不进入节点资源定义，不生成运行时端口。
4. 支持通过 IO Handle 与目标节点绑定 Handle 手动建立绑定关系。
5. 保留“拖动整个 IO 节点到目标节点本体”的快速绑定方式。
6. 输入绑定关系使用淡蓝色，输出绑定关系使用淡紫色。
7. 绑定目标节点使用与关系方向对应的常驻边框。
8. 绑定关系使用独立于数据边的虚线或连接线展示。
9. 同一个绑定 Handle 支持多个同方向 IO，但不允许同一目标节点混合绑定输入和输出 IO。
10. 第一阶段只允许绑定图的起始节点或结束节点，不允许绑定中间节点。
11. 前后端使用同一套结构约束，前端负责即时提示，后端负责权威校验。
12. 已有不可变 Revision 的执行结果不被新规则修改。

### 3.2 质量目标

1. 绑定关系和数据关系在数据模型、视觉样式和运行时编译中完全分离。
2. 编译结果不依赖节点遍历顺序或 Compiler Adapter 注册顺序。
3. 图结构发生变化后，绑定有效性能够立即重新计算。
4. 非法历史绑定可以被识别、解释和修复，不进行静默重写。
5. 所有关键规则具有单元测试和端到端测试。
6. 不增加新的前端或后端第三方依赖。

### 3.3 非目标

本次重构不实现以下能力：

1. 不实现任意中间节点切分成多个可独立调用子图。
2. 不实现“直接暴露普通节点真实输入、输出端口且继续执行该节点”的新语义。
3. 不允许绑定 Handle 参与普通数据传输。
4. 不把绑定关系保存为普通 `GraphEdgeSchema` 数据边。
5. 不修改已发布不可变 Revision 的图快照和执行计划。
6. 不允许前端配置绕过后端结构校验。

---

## 4. 术语和概念

### 4.1 IO 节点

IO 节点包括：

- 蓝图输入节点：`blueprint.input`
- 蓝图输出节点：`blueprint.output`

IO 节点是设计图中的真实节点。每个 IO 节点生成一个稳定的公开接口端口。

### 4.2 普通数据 Handle

节点定义中的真实输入、输出 Handle，参与以下行为：

- Vue Flow 普通连线；
- `GraphEdgeSchema` 持久化；
- 端口类型兼容校验；
- 执行图依赖计算；
- 节点运行时数据传输；
- 封装节点公开 Handles 生成。

### 4.3 虚拟绑定 Handle

非 IO 节点顶部的统一绑定入口：

- 只用于建立和展示绑定替换关系；
- 不属于 `ActionNodeHandleModel`；
- 不写入节点定义的 `handles`；
- 不写入 `GraphEdgeSchema`；
- 不参与端口兼容和运行时数据传输；
- 可关联多个 IO 节点；
- 在界面上只显示为一个 Handle。

### 4.4 普通数据边

真实数据传输关系，保存在蓝图 `graph.edges` 中，必须连接真实 `source` 和 `target` Handle。

### 4.5 绑定关系线

由 IO 节点的 `boundary_binding` 派生出的只读展示关系：

- 不进入保存请求；
- 不进入编译器输入图；
- 不计算入度、出度；
- 不参与循环检测；
- 不允许通过普通删除边操作直接删除；
- 删除关系必须执行“解绑 IO”。

### 4.6 绑定替换

绑定的现有核心语义保持不变：

- 独立运行：IO 节点被跳过，目标节点正常执行。
- 封装运行：IO 节点保留，目标节点被跳过，IO 节点替代目标节点被映射的端口。

因此，绑定不是简单地给目标节点标记入口或出口，而是改变封装运行时实际执行图。

### 4.7 入口替代和出口替代

- 输入 IO 绑定目标节点：目标节点承担“入口替代目标”角色，封装运行时由父流程输入替代目标节点输出。
- 输出 IO 绑定目标节点：目标节点承担“出口替代目标”角色，封装运行时将原本进入目标节点的数据返回父流程。

为避免“输入节点绑定输出端口”等方向描述产生歧义，前端面向用户优先使用“入口替代”和“出口替代”文案。

### 4.8 公开接口类型继承

IO 原生节点定义中的 `builtin.value` 仅是编辑器内部的占位传输端口，不作为最终公开接口类型。公开接口按编译后的真实数据流推导：

- 输入 IO 绑定起始节点时，继承重连后下游节点 target Handle 的配置和接口类型；
- 输出 IO 绑定结束节点时，继承重连前上游节点 source Handle 的配置和接口类型；
- 未绑定但已有普通数据边的 IO，直接继承数据边另一端的 Handle；
- 未绑定且没有数据边的独立 IO，必须从后端动态返回的已有 Handle 配置中选择；
- 一个 IO 对应多个相邻 Handle 时，这些 Handle 的 `handle_config_id`、`interface_type_id` 和数据类型必须完全一致，否则应拆分为多个 IO。

虚拟绑定 Handle 只负责声明替换关系，不参与数据传输，也不进行接口类型匹配。输入 IO 仍只能映射目标 source 端口，输出 IO 仍只能映射目标 target 端口。

---

## 5. 当前实现基线

### 5.1 持久化模型

当前结构可以继续复用：

```python
class BoundaryPortMapping(BaseModel):
    interface_port_id: str
    target_port_id: str


class BoundaryBinding(BaseModel):
    bound_node_id: str
    port_mappings: list[BoundaryPortMapping]
```

方向不保存在 `BoundaryBinding` 中，而是根据 IO 节点定义推导：

- `blueprint.input` 推导为 `input`；
- `blueprint.output` 推导为 `output`。

每个 IO 节点最多绑定一个目标节点，但一个目标节点可以被多个 IO 节点引用。

### 5.2 当前前端行为

当前前端：

1. 通过 `getBindableHandles` 检查目标端口方向、连线覆盖和占用状态。
2. 通过节点重叠判定拖放目标。
3. 通过 `BoundaryBindingDialog` 选择一个或多个目标端口。
4. 通过 `bound_node_id` 和 `port_mappings` 保存关系。
5. 通过 `bindingDisplay` 展示 IO 节点的绑定摘要。
6. 通过 `bindingTargetKinds` 派生目标节点边框。
7. 新建绑定时，输入 IO 自动定位到目标节点左上方，输出 IO 自动定位到右上方；之后位置由用户自由调整。

当前未检查：

- 目标是否为图的起始或结束节点；
- 目标是否已被另一方向 IO 绑定；
- 已绑定 IO 是否仍存在普通数据边；
- 图修改后原绑定是否仍然有效；
- 目标节点所有被替换边是否得到完整重写。

### 5.3 当前编译行为

输入绑定在封装运行中：

1. 跳过目标节点。
2. 删除目标节点全部关联边。
3. 找出目标节点被映射的输出端口。
4. 将这些输出端口的原下游边改为从输入 IO 发出。

输出绑定在封装运行中：

1. 跳过目标节点。
2. 删除目标节点全部关联边。
3. 找出目标节点被映射的输入端口。
4. 将这些输入端口的原上游边改为进入输出 IO。

当前重复占用键为：

```text
(direction, bound_node_id, target_port_id)
```

因此同一目标端口不能被多个同方向 IO 重复替换，但输入和输出方向互不冲突。

### 5.4 当前中间节点问题

原图：

```text
A -> B -> C
```

B 绑定输入 IO 后：

```text
A

Input_B -> C
```

B 绑定输出 IO 后：

```text
A -> Output_B

C
```

B 同时绑定输入、输出 IO 后：

```text
A -> Output_B

Input_B -> C
```

该结果是两个断开的执行分支，不是自动生成的两个可管理子蓝图。

如果 A、B、C 又分别被其他 IO 替换，编译器生成的新边可能引用其他已跳过节点，并在有效边过滤阶段被删除，最终可能只剩互不连通的 IO 节点。当前校验允许孤立节点，因此这种图可能成功保存或发布。

---

## 6. 核心设计决策

### 6.1 保持“节点替换”语义

本阶段不改变 `boundary_binding` 的核心含义。选择保持兼容的原因：

1. 已有编译器、Revision 和封装节点都基于替换语义。
2. 独立运行和封装运行之间切换真实来源、接收端的能力依赖替换语义。
3. 如果改为“暴露节点端口且继续执行节点”，将改变已有蓝图行为。

如果业务需要暴露普通节点端口且节点继续运行，应在未来设计独立的“端口暴露”功能。

### 6.2 使用一个可见绑定 Handle

每个目标节点最多展示一个绑定 Handle。该 Handle：

- 不分蓝色输入接口和紫色输出接口；
- 可绑定多个 IO；
- 根据正在连接的 IO 类型推导方向；
- 根据目标节点当前绑定角色限制后续连接；
- 通过关系线颜色表达输入、输出差异。

### 6.3 禁止同一目标混合方向

同一 `bound_node_id` 下只能出现一种 IO 方向：

```text
directions(bound_node_id) 的集合大小必须小于等于 1
```

合法：

```text
Input_1 --\
Input_2 ----> Target_A
Input_3 --/
```

合法：

```text
Output_1 --\
Output_2 ----> Target_C
Output_3 --/
```

非法：

```text
Input_1  --> Target_B
Output_1 --> Target_B
```

### 6.4 允许多个同方向 IO

统一绑定 Handle 不限制 IO 数量。后端继续按目标真实端口判断冲突：

- 不同 IO 可映射同一目标节点的不同端口；
- 一个 IO 可映射目标节点的多个端口；
- 同一个目标端口不能被多个同方向 IO 重复映射。

### 6.5 第一阶段禁止中间节点绑定

入口替代目标必须是设计数据图的起始节点：

```text
in_degree(target) == 0
```

出口替代目标必须是设计数据图的结束节点：

```text
out_degree(target) == 0
```

计算入度、出度时：

- 只统计持久化的普通数据边；
- 统计所有节点之间的普通数据边，包括未绑定 IO 节点的数据边；
- 忽略虚拟绑定关系线；
- 忽略画布位置和节点重叠关系。

这意味着：

- 已被未绑定输入 IO 通过普通数据边连接的节点不再是起始节点；
- 已连接未绑定输出 IO 的节点不再是结束节点；
- 独立孤立节点虽然同时满足零入度、零出度，但没有可重写数据边，不能完成有效绑定。

### 6.6 绑定模式与普通连线模式互斥

一个 IO 节点只能处于以下一种模式：

1. 独立模式：`boundary_binding == null`，允许普通数据边。
2. 绑定模式：`boundary_binding != null`，不允许任何普通数据边。

建立绑定前，如果 IO 节点已有普通数据边：

- 前端不得静默删除；
- 默认阻止绑定；
- 提示用户先删除普通数据连线；
- 后续如果增加批量转换操作，必须单独确认删除范围。

已绑定 IO 节点上尝试创建普通数据边时，应提示先解绑。

### 6.7 替换端口必须真实参与数据流

为了避免公开接口没有任何实际作用：

- 输入绑定映射的每个目标输出端口必须至少存在一条原始出边；
- 输出绑定映射的每个目标输入端口必须至少存在一条原始入边。

为了避免目标节点被跳过后部分分支静默丢失，同一目标节点同方向全部 IO 的映射并集必须覆盖该目标节点所有已连接的可替换端口：

```text
输入绑定：
connected_source_ports(target) == mapped_source_ports(target)

输出绑定：
connected_target_ports(target) == mapped_target_ports(target)
```

只要求覆盖具有实际数据边的端口；未连接端口不需要映射。

### 6.8 图编辑后实时失效

以下操作可能改变绑定有效性：

- 新增或删除普通数据边；
- 修改边的源端口或目标端口；
- 删除目标节点；
- 删除或升级节点定义；
- 修改 Handle 稳定 `port_id`；
- 将起始节点变成中间节点；
- 将结束节点变成中间节点；
- 新增另一方向 IO 绑定；
- 给已绑定 IO 增加普通数据边。

前端必须重新计算绑定状态。已有非法绑定不能被静默解除，而应：

1. 保留原始绑定数据；
2. 将关系线和目标节点标记为错误状态；
3. 展示具体原因；
4. 阻止保存、发布和封装；
5. 允许用户解绑或修改图结构修复。

后端在创建、更新、校验、发布、封装时执行相同规则。

---

## 7. 正式约束

设：

- `V`：设计图全部节点；
- `E`：持久化普通数据边；
- `B`：IO 节点集合；
- `N = V - B`：非 IO 节点集合；
- `binding(b)`：IO 节点 `b` 的 `boundary_binding`；
- `direction(b)`：IO 节点方向；
- `target(b)`：`binding(b).bound_node_id`；
- `ports(b)`：`binding(b).port_mappings.target_port_id` 集合。

### 7.1 目标存在性

对所有已绑定 IO 节点：

```text
target(b) ∈ N
```

禁止绑定：

- 不存在的节点；
- 蓝图输入节点；
- 蓝图输出节点；
- 当前蓝图之外的节点；
- 已禁用或定义缺失的节点。

### 7.2 方向约束

输入 IO：

```text
ports(b) ⊆ source_handles(target(b))
```

输出 IO：

```text
ports(b) ⊆ target_handles(target(b))
```

### 7.3 端点约束

输入 IO：

```text
in_degree_E(target(b)) == 0
```

输出 IO：

```text
out_degree_E(target(b)) == 0
```

### 7.4 单目标单角色

对任意非 IO 节点 `n`：

```text
|{direction(b) | target(b) == n}| <= 1
```

### 7.5 端口占用唯一

对任意方向、目标节点和目标端口组合：

```text
(direction, target_node_id, target_port_id)
```

最多只能被一个 IO 节点声明。

### 7.6 端口覆盖完整

对被输入 IO 绑定的目标节点：

```text
所有存在普通出边的 source 端口
必须被该目标节点的输入 IO 映射并集覆盖。
```

对被输出 IO 绑定的目标节点：

```text
所有存在普通入边的 target 端口
必须被该目标节点的输出 IO 映射并集覆盖。
```

### 7.7 IO 模式互斥

```text
binding(b) != null
=> 不存在 edge.source == b.id 或 edge.target == b.id
```

### 7.8 接口类型

绑定端口不与 IO 原生占位 Handle 比较类型。编译器完成替换后，从公开接口实际连接的相邻 Handle 继承：

- `handle_config_id`；
- `interface_type_id`；
- `data_type`；
- 显示标签、颜色和兼容类型。

同一公开接口对应多个相邻 Handle 时，上述核心类型签名必须完全一致。

### 7.9 接口身份

每个 IO 节点必须满足：

- `interface_name` 非空；
- 同方向 `interface_name` 唯一；
- `interface_port_id` 非空且稳定；
- `port_mappings.interface_port_id` 必须等于当前 IO 节点的 `interface_port_id`。

---

## 8. 目标运行语义

### 8.1 独立运行

独立运行时：

1. 所有 IO 节点标记为 `SKIPPED`。
2. 删除 IO 节点的普通数据边。
3. 被绑定目标节点正常执行。
4. 目标节点原有普通数据边保持不变。
5. 虚拟绑定关系不进入执行计划。
6. 根据处理后的图重新计算入度、出度和起始节点。

即使绑定关系只在封装运行中生效，蓝图保存和发布仍必须通过完整绑定结构校验。

### 8.2 封装运行

输入绑定：

1. 输入 IO 保留。
2. 入口替代目标节点跳过。
3. 删除目标节点关联边。
4. 将目标节点已映射输出端口的所有出边改为从对应输入 IO 发出。

输出绑定：

1. 输出 IO 保留。
2. 出口替代目标节点跳过。
3. 删除目标节点关联边。
4. 将原本进入目标节点已映射输入端口的所有入边改为进入对应输出 IO。

### 8.3 多 IO 替换同一目标

所有绑定声明必须先收集、整体校验，再统一生成图变更，不能逐个修改共享图。

示例：

```text
             left  -> L
SourceNode
             right -> R
```

两个输入 IO 分别绑定 `left`、`right`：

```text
InputLeft  -> L
InputRight -> R
```

`SourceNode` 只跳过一次，两个端口的原始下游边全部得到重写。

### 8.4 不自动要求每个输入到达每个输出

行动蓝图可能包含：

- 只产生副作用的输入分支；
- 不依赖公开输入的定时或常量分支；
- 多个彼此独立的输入输出分支。

因此不要求“每个公开输入都能到达每个公开输出”。但必须保证：

- 每个绑定输入至少重写一条真实出边；
- 每个绑定输出至少接收一条真实入边；
- 被替换目标的所有已连接可替换端口均被覆盖；
- 绑定不能制造因中间节点替换导致的非预期断裂。

---

## 9. 数据模型设计

### 9.1 保持现有持久化结构

第一阶段不修改 `BoundaryBinding`：

```json
{
  "bound_node_id": "node-a",
  "port_mappings": [
    {
      "interface_port_id": "public-input-a",
      "target_port_id": "source-port-a"
    }
  ]
}
```

原因：

1. 已能表达一个 IO 绑定一个目标、映射多个端口。
2. 已能通过多个 IO 节点表达目标绑定多个 IO。
3. 绑定方向可从 IO 节点定义稳定推导。
4. 虚拟绑定 Handle 不需要持久化身份。
5. 可避免数据库结构迁移。

### 9.2 不保存虚拟 Handle

禁止向节点定义追加以下伪端口：

```text
__boundary_binding__
```

虚拟 Handle 不得进入：

- `ActionNodeHandleModel`；
- 节点资源配置；
- `GraphNodeSchema.data`；
- `GraphEdgeSchema`；
- 封装节点生成 Handles；
- Revision 定义快照；
- 执行计划。

### 9.3 前端派生状态

建议统一生成只读状态：

```javascript
{
  role: 'entry' | 'exit' | null,
  boundaryNodeIds: [],
  relationCount: 0,
  canAcceptInput: false,
  canAcceptOutput: false,
  valid: true,
  issueCodes: []
}
```

该状态由当前节点、普通数据边和所有 IO 的 `boundaryBinding` 计算，不写入保存请求。

当前 `bindingTargetKinds`、`bindingDisplay` 可以在过渡期保留，但最终应统一由上述派生模型提供。

### 9.4 可选节点定义策略

第一阶段默认根据图结构自动判断是否展示绑定 Handle，不要求创建节点时手工配置。

如果后续需要禁止某类节点参与绑定，可在节点定义扩展配置中增加：

```json
{
  "boundary_binding_policy": {
    "mode": "auto",
    "allowed_directions": ["input", "output"]
  }
}
```

建议支持：

- `mode = auto`：按结构自动判断；
- `mode = disabled`：不允许绑定；
- `allowed_directions`：进一步限制允许的 IO 类型。

该策略只能收紧权限，不能允许中间节点绕过端点约束。前端和后端必须共同读取该策略。

---

## 10. 后端重构设计

### 10.1 校验分层

校验分为三层：

#### 局部绑定校验

由边界 Compiler Adapter 负责：

- IO 节点接口名称和稳定端口；
- 绑定目标存在；
- 目标不是 IO 节点；
- 目标端口方向；
- 端口类型兼容；
- `port_mappings` 非空；
- 单个 IO 内部没有重复目标端口；
- `interface_port_id` 引用正确。

#### 全局绑定校验

由编译器在收集所有 Adapter 声明后负责：

- 同一目标是否混合输入和输出；
- 同方向目标端口是否重复占用；
- 输入目标是否为起始节点；
- 输出目标是否为结束节点；
- 已绑定 IO 是否仍有普通数据边；
- 映射端口是否真实参与普通数据边；
- 映射并集是否完整覆盖已连接端口。

#### 执行图校验

完成图重写后继续执行：

- 节点和边身份唯一；
- 不存在指向已跳过节点的有效边；
- 不存在执行图悬空边；
- 不存在循环；
- 有效入度、出度计算正确。

### 10.2 Adapter 声明式输出

为了避免 `BlueprintCompiler` 直接判断 `blueprint.input`、`blueprint.output` Handler 名称，边界 Adapter 应输出稳定的绑定声明：

```python
{
    "boundary_node_id": "...",
    "direction": "input",
    "bound_node_id": "...",
    "target_port_ids": ["..."],
}
```

编译器只处理该稳定协议，不依赖具体 Handler 名称。

所有 Adapter 先针对不可变设计图产生声明，再由编译器：

1. 收集声明；
2. 执行全局校验；
3. 合并 `skip_nodes`；
4. 合并待删除边；
5. 合并新增边；
6. 构建有效执行图。

### 10.3 避免顺序依赖

不得在遍历第一个 IO 时直接修改共享图，再让后续 IO 读取修改后的图。以下情况必须得到确定结果：

- 多个 IO 绑定同一目标不同端口；
- 多个目标分别被 IO 替换；
- 节点顺序改变；
- Adapter 注册顺序改变；
- 图节点 ID 排序改变。

### 10.4 结构化校验问题

复用 `BlueprintValidationIssue`，建议增加以下错误码：

| 错误码 | 含义 |
|---|---|
| `binding_target_not_found` | 目标节点不存在 |
| `binding_target_is_boundary` | 目标节点也是 IO 节点 |
| `binding_target_not_start` | 输入绑定目标不是起始节点 |
| `binding_target_not_end` | 输出绑定目标不是结束节点 |
| `binding_mixed_direction` | 同一目标混合输入、输出绑定 |
| `binding_duplicate_target_port` | 同方向重复占用目标端口 |
| `binding_empty_mapping` | 没有目标端口映射 |
| `binding_port_direction_invalid` | 目标端口方向错误 |
| `boundary_exposed_handle_mismatch` | 一个公开接口对应了不同类型的相邻 Handle |
| `binding_port_not_connected` | 映射端口没有真实数据边 |
| `binding_port_coverage_incomplete` | 已连接端口没有被完整映射 |
| `binding_boundary_has_data_edge` | 已绑定 IO 仍存在普通数据边 |
| `binding_interface_invalid` | 接口名称或稳定端口无效 |

问题结构示例：

```json
{
  "code": "binding_mixed_direction",
  "message": "节点 B 不能同时作为入口替代目标和出口替代目标",
  "node_id": "input-boundary-id",
  "details": {
    "target_node_id": "node-b",
    "related_boundary_node_ids": [
      "input-boundary-id",
      "output-boundary-id"
    ]
  }
}
```

### 10.5 API 行为

以下入口必须执行相同的绑定校验：

- 创建蓝图；
- 更新蓝图；
- 校验蓝图；
- 发布 Revision；
- 封装为节点；
- 从蓝图创建分支后首次保存。

`POST /action/blueprint/{id}/validate` 应通过现有 `errors`、`warnings` 返回结构化问题，而不是只返回统一的 `blueprint_invalid`。

创建、更新接口可以继续保持现有错误响应外层结构，但应尽可能在响应详情中返回具体问题，便于前端定位节点。

### 10.6 编译器文件调整

主要涉及：

- `csi-back/app/service/native_nodes/compiler_registry.py`
- `csi-back/app/service/action_compiler.py`
- `csi-back/app/schemas/action/interface.py`
- `csi-back/app/api/v1/endpoints/action/blueprint.py`
- `csi-back/app/service/blueprint_revision.py`

如果全局绑定规则继续增长，可新增专用模块：

```text
csi-back/app/service/boundary_binding_validator.py
```

该模块应被创建、更新、校验、发布和编译流程共同复用，不能在不同接口中复制规则。

---

## 11. 前端重构设计

### 11.1 单一可见绑定 Handle

新增建议组件：

```text
csi-front/src/components/action/nodes/components/BoundaryBindingAnchor.vue
```

组件职责：

1. 在非 IO 节点顶部中央显示一个小型绑定 Handle。
2. 根据派生状态决定可见、禁用或错误状态。
3. 显示已绑定 IO 数量。
4. 悬停显示能力和绑定摘要。
5. 作为手动连接的命中区域。
6. 不参与表单和普通 Handle 布局计算。

推荐视觉：

- 外形：小圆点、菱形或链环；
- 尺寸：6px 至 8px，命中区域不小于 20px；
- 未绑定：中性灰；
- 可接受当前 IO：蓝色或紫色高亮；
- 已绑定入口：淡蓝色；
- 已绑定出口：淡紫色；
- 非法绑定：红色；
- 多绑定：角标展示数量。

### 11.2 Vue Flow 方向适配

Vue Flow 的原生 Handle 必须是 `source` 或 `target`。界面上只显示一个绑定 Handle，但内部可以采用以下实现之一：

#### 推荐方案：单一视觉层 + 两个重叠协议端点

- 一个可见的 `BoundaryBindingAnchor`；
- 内部放置两个透明、同位置的 Vue Flow Handle；
- 保留两个内部保留 ID：

```text
__boundary_binding_source__
__boundary_binding_target__
```

- 输入 IO 的 source 连接内部 target；
- 内部 source 连接输出 IO 的 target；
- 用户只看到一个绑定 Handle，不感知内部方向端点；
- `onConnect` 识别保留 ID 后进入绑定流程，不增加数据边。

内部存在两个协议端点不等于产品上存在两个绑定接口。它们只是对 Vue Flow 严格方向模型的适配。

#### 可选方案：完全自定义指针交互

不使用 Vue Flow Handle，独立实现绑定拖动预览和命中检测。该方案控制力更强，但需要自行处理：

- 坐标变换；
- 缩放；
- 画布平移；
- 指针捕获；
- 自动滚动；
- 连接预览线；
- 取消连接。

第一阶段优先使用“双协议端点、单一视觉层”方案。

### 11.3 Handle 展示条件

非 IO 节点根据普通数据边实时推导：

```text
canAcceptInput =
    入度为 0
    且存在 source Handle
    且未锁定为出口角色

canAcceptOutput =
    出度为 0
    且存在 target Handle
    且未锁定为入口角色
```

显示规则：

- 两者均为 `false`：默认不显示；
- 任意一个为 `true`：显示统一绑定 Handle；
- 已存在绑定：始终显示，即使关系已失效；
- 已失效：显示错误状态，允许悬停查看原因和执行解绑；
- 节点禁用或只读：显示关系但禁止新建、修改。

对于尚未连接任何数据边的孤立节点，可以显示禁用态绑定 Handle，并提示“请先完成普通数据流连接”，避免用户误以为节点不支持绑定。

### 11.4 手动连接流程

#### 输入 IO

```text
蓝图输入真实 source Handle
    -> 目标节点统一绑定 Handle
```

流程：

1. 用户开始拖动蓝图输入 Handle。
2. 可接受输入绑定的目标 Handle 高亮。
3. 连接到目标后，`onConnect` 识别绑定协议端点。
4. 不调用 `addEdges`。
5. 打开绑定对话框。
6. 选择目标节点真实输出端口。
7. 确认后写入 IO 节点 `boundaryBinding`。
8. 生成派生绑定关系线和目标边框。

#### 输出 IO

受 Vue Flow 严格方向限制，标准方向为：

```text
目标节点统一绑定 Handle
    -> 蓝图输出真实 target Handle
```

第一阶段同时提供“点击输出 IO Handle，再点击目标绑定 Handle”的连接方式，使用户可以从输出 IO 一侧发起操作。两次点击之间展示绑定预览线，按 `Esc`、点击画布空白或切换节点时取消。

本阶段不要求把 Vue Flow 全局改为宽松连接模式，也不自行重写完整的画布指针系统。拖动方向和点击方向最终都进入同一个绑定流程。

### 11.5 保留整卡拖动快速绑定

原有操作继续保留：

1. 从节点面板拖动 IO 节点到目标节点；
2. 或将画布上的未绑定 IO 节点拖动到目标节点；
3. 候选目标满足结构规则时高亮；
4. 松开后打开端口映射对话框。

整卡拖动和 Handle 手动连接必须调用同一个绑定服务函数，不能分别实现不同校验。

建议统一入口：

```javascript
requestBoundaryBinding(boundaryNode, targetNode, trigger)
```

其中 `trigger` 仅用于埋点和界面提示，不改变业务规则。

### 11.6 绑定候选效果

拖动 IO 节点或绑定连线时：

- 可接受目标：对应方向的淡色背景光晕；
- 当前命中目标：边框加深，绑定 Handle 放大；
- 角色冲突目标：红色或禁用光标，并显示原因；
- 中间节点：不高亮，悬停提示“绑定替换仅支持起始或结束节点”；
- 类型不兼容：提示“没有兼容的可替换端口”；
- 已绑定同方向且仍有空闲端口：允许继续绑定；
- 已绑定同方向但端口全部占用：禁用；
- 已绑定另一方向：禁用。

### 11.7 绑定关系线

绑定关系线从 `boundaryBinding` 派生：

```javascript
{
  id: `binding:${boundaryNodeId}:${targetNodeId}`,
  relationKind: 'boundary-binding',
  direction: 'input' | 'output',
  source: '...',
  target: '...',
  selectable: false,
  deletable: false
}
```

展示要求：

- 输入绑定：蓝色、较细虚线；
- 输出绑定：紫色、较细虚线；
- 不使用普通数据边箭头样式；
- 可使用链环图标或小圆点强调“关系而非数据”；
- 连接目标为节点顶部统一绑定 Handle；
- 多条关系线允许汇聚到同一个 Handle；
- 悬停关系线显示 IO 名称、目标节点、映射端口；
- 非法关系使用红色虚线。

如果派生关系线临时放入 Vue Flow 的 edges 集合，保存时必须显式过滤：

```text
edge.data.relationKind == "boundary-binding"
```

更推荐单独维护 `bindingRelationEdges`，避免 `getEdges()`、普通删除边、边校验和保存逻辑误处理。

### 11.8 IO 节点展示

输入、输出 IO 节点继续使用 `GenericNode` 和通用输入组件，不新增重复表单体系。

视觉规则：

- 输入 IO 背景：淡蓝色；
- 输出 IO 背景：淡紫色；
- 不使用与普通节点结构不一致的额外外框；
- 绑定摘要显示目标节点和真实端口；
- 新建输入绑定时，IO 节点自动定位到目标节点左上方；
- 新建输出绑定时，IO 节点自动定位到目标节点右上方；
- 同方向多个 IO 继续向左或向右排列，避免初始位置重叠；
- 自动定位只在首次绑定或改绑到另一目标节点时执行一次；
- 加载蓝图、移动目标节点和节点尺寸变化时不重新定位 IO；
- 用户可自由移动已绑定 IO，位置按普通节点保存和恢复。

### 11.9 目标节点展示

目标节点边框：

- 入口替代：`2px solid #93c5fd`；
- 出口替代：`2px solid #c4b5fd`；
- 非法或历史混合绑定：红色错误边框；
- 执行状态边框优先级高于绑定边框。

当执行状态边框覆盖绑定边框时，绑定关系仍通过以下元素保持可见：

- 顶部绑定 Handle 颜色；
- 绑定数量徽标；
- 蓝色或紫色关系线；
- 节点角落的绑定角色标记。

目标规则禁止混合方向后，不再把“蓝色边框 + 紫色外轮廓”视为合法最终状态。该样式只可用于迁移期间识别历史冲突，最终应改为错误状态。

### 11.10 尺寸和布局稳定性

绑定 Handle 和边框必须相对节点根元素定位，不能依赖左侧节点列表宽度或固定屏幕坐标。

以下情况需要刷新 Vue Flow 节点内部尺寸和关系线路径：

- 节点表单内容变化；
- 节点列表侧栏宽度变化；
- 浏览器窗口变化；
- 节点折叠或展开；
- 节点定义升级；
- 绑定摘要显示或隐藏；
- 多个绑定 IO 重新排列。

优先使用 Vue Flow 节点坐标和 dimensions，不通过 DOM 重叠结果长期保存关系。DOM 命中只用于当前拖放候选识别。

### 11.11 对话框

`BoundaryBindingDialog` 继续复用，调整内容：

- 标题：建立入口替代绑定 / 建立出口替代绑定；
- 明确提示“封装运行时目标节点不会执行”；
- 展示目标节点当前角色和已绑定 IO 数量；
- 只展示方向、类型兼容且未被其他 IO 占用的端口；
- 已由当前 IO 映射的端口仍可勾选；
- 被其他 IO 占用的端口显示占用者；
- 显示尚未覆盖的已连接端口；
- 未完整覆盖时允许继续编辑，但确认或保存前必须提示；
- 提供解绑入口；
- 不静默删除普通数据边。

### 11.12 无障碍和提示

绑定 Handle 至少提供：

- `aria-label`；
- 键盘聚焦；
- 悬停提示；
- 已绑定数量文本；
- 禁用原因。

建议文案：

- 未绑定：“绑定：用蓝图 IO 替代该节点，封装运行时该节点不会执行”
- 入口角色：“入口替代：已绑定 2 个蓝图输入”
- 出口角色：“出口替代：已绑定 1 个蓝图输出”
- 中间节点：“当前节点位于流程中间，不能作为绑定替换目标”
- 方向冲突：“该节点已作为入口替代目标，不能再绑定蓝图输出”

---

## 12. 前端派生算法

建议在 `boundaryBinding.js` 中集中实现纯函数，避免 Vue 组件分别计算。

### 12.1 构建图索引

```javascript
buildDataGraphIndex(nodes, edges) => {
  inDegreeByNode,
  outDegreeByNode,
  incomingEdgesByNode,
  outgoingEdgesByNode,
  nodeById
}
```

输入 edges 必须只包含普通数据边。

### 12.2 收集目标绑定

```javascript
collectBindingsByTarget(nodes) => {
  [targetNodeId]: {
    directions,
    boundaryNodes,
    occupiedPortIds
  }
}
```

### 12.3 计算目标状态

```javascript
resolveBindingTargetState(targetNode, graphIndex, bindingsByTarget)
```

输出至少包含：

- 当前角色；
- 可接受方向；
- 已绑定 IO；
- 已占用端口；
- 是否为起始节点；
- 是否为结束节点；
- 是否存在方向冲突；
- 是否存在普通边模式冲突；
- 是否存在未覆盖端口；
- 结构化问题列表。

### 12.4 校验一次连接

```javascript
validateBindingCandidate(boundaryNode, targetNode, context)
```

返回：

```javascript
{
  valid: true,
  bindableHandles: [],
  issues: []
}
```

整卡拖动、手动 Handle 连接、对话框和保存前校验必须复用该函数。

### 12.5 派生关系线

```javascript
buildBindingRelationEdges(nodes, targetStates)
```

只用于展示，不参与保存。

---

## 13. 交互状态机

### 13.1 IO 节点状态

```text
UNBOUND
  ├─ 普通数据连线 ─> INDEPENDENT_CONNECTED
  └─ 请求绑定 ─────> BINDING_PENDING

INDEPENDENT_CONNECTED
  ├─ 删除全部数据边 ─> UNBOUND
  └─ 请求绑定 ───────> 阻止并提示

BINDING_PENDING
  ├─ 确认 ─> BOUND
  └─ 取消 ─> 原状态

BOUND
  ├─ 修改端口 ─> BINDING_PENDING
  ├─ 解绑 ─────> UNBOUND
  ├─ 创建数据边 ─> 阻止并提示
  └─ 图结构失效 ─> BOUND_INVALID

BOUND_INVALID
  ├─ 修复图结构 ─> BOUND
  ├─ 修改绑定 ───> BINDING_PENDING
  └─ 解绑 ───────> UNBOUND
```

### 13.2 目标节点角色状态

```text
NONE
  ├─ 绑定输入 IO ─> ENTRY
  └─ 绑定输出 IO ─> EXIT

ENTRY
  ├─ 继续绑定输入 IO ─> ENTRY
  ├─ 绑定输出 IO ─────> 拒绝
  └─ 解绑最后一个输入 ─> NONE

EXIT
  ├─ 继续绑定输出 IO ─> EXIT
  ├─ 绑定输入 IO ─────> 拒绝
  └─ 解绑最后一个输出 ─> NONE

任意状态
  └─ 图结构不再满足约束 ─> INVALID
```

---

## 14. 典型场景

### 14.1 正常单入口单出口

设计图：

```text
Source_A -> Work_B -> Sink_C
```

绑定：

- `Input_A` 绑定 `Source_A` 的输出端口；
- `Output_C` 绑定 `Sink_C` 的输入端口。

封装运行：

```text
Input_A -> Work_B -> Output_C
```

### 14.2 一个入口目标绑定多个输入

设计图：

```text
            left  -> Work_L
Source_A
            right -> Work_R
```

绑定：

- `Input_Left` 映射 `Source_A.left`；
- `Input_Right` 映射 `Source_A.right`。

封装运行：

```text
Input_Left  -> Work_L
Input_Right -> Work_R
```

两个 IO 共用 `Source_A` 顶部同一个可见绑定 Handle。

### 14.3 目标端口重复

两个输入 IO 都映射 `Source_A.left`：

```text
Input_1 -> Source_A.left
Input_2 -> Source_A.left
```

结果：

- 前端第二次绑定时禁用该端口；
- 后端返回 `binding_duplicate_target_port`；
- 不允许保存或发布。

### 14.4 中间节点绑定

设计图：

```text
A -> B -> C
```

尝试给 B 绑定任意 IO：

- 前端 B 不作为有效候选；
- B 的绑定 Handle 默认不显示；
- 通过旧数据或构造请求提交时后端拒绝；
- 输入 IO 返回 `binding_target_not_start`；
- 输出 IO 返回 `binding_target_not_end`。

### 14.5 同一目标混合方向

给 A 同时绑定输入和输出 IO：

- 首次绑定决定 A 的角色；
- 第二方向在前端被拒绝；
- 历史数据加载时显示红色非法关系；
- 后端返回 `binding_mixed_direction`。

### 14.6 绑定后修改图结构

原图：

```text
A -> B
```

A 已绑定输入 IO。用户新增：

```text
X -> A
```

结果：

- A 不再是起始节点；
- 原绑定保留但标记失效；
- 关系线变红；
- 保存被阻止；
- 用户可删除 `X -> A` 或解绑输入 IO。

### 14.7 一个节点同时公开输入输出且继续执行

需求：

```text
父流程输入 -> B -> 父流程输出
```

该需求不能通过把输入、输出 IO 都绑定到 B 实现，因为绑定会跳过 B。

正确方向：

- 当前可在 B 前后分别使用独立 IO 普通数据连线；或
- 未来实现“端口暴露”功能，使 B 保持执行。

---

## 15. 历史数据和迁移

### 15.1 兼容原则

1. 不修改不可变 Revision。
2. 不重新编译已发布 Revision 的执行计划快照。
3. 已封装节点继续引用原 Revision。
4. 当前可编辑蓝图继续可读取。
5. 新规则只影响后续创建、更新、发布和重新封装。
6. 不静默删除绑定、端口映射或普通数据边。

### 15.2 需要审计的历史情况

迁移审计至少识别：

- 中间节点绑定；
- 同一目标输入、输出混合绑定；
- 已绑定 IO 仍有普通数据边；
- 同方向重复目标端口；
- 映射端口不存在；
- 映射端口方向错误；
- 映射端口类型不兼容；
- 映射端口没有普通数据边；
- 被替换目标已连接端口未完整覆盖；
- 目标节点不存在；
- 目标节点本身是 IO 节点。

### 15.3 迁移策略

不建议自动改变业务图。建议分为：

#### 第一步：只读审计

提供脚本或服务方法输出：

- 扫描蓝图总数；
- 合法蓝图数；
- 各问题数量；
- 问题蓝图 ID；
- 边界节点 ID；
- 目标节点 ID；
- 修复建议。

#### 第二步：兼容读取

非法蓝图仍可打开，前端显示：

- 顶部错误提示；
- 问题节点定位；
- 非法关系红色展示；
- 具体修复建议。

#### 第三步：阻止新写入

非法蓝图不能：

- 保存修改；
- 发布新 Revision；
- 重新封装；
- 创建引用最新草稿的新节点版本。

已有 Revision 和历史行动不受影响。

### 15.4 修复建议

| 历史问题 | 建议修复 |
|---|---|
| 中间节点绑定 | 移动绑定到起始或结束占位节点 |
| 混合方向绑定 | 拆到不同入口、出口目标节点 |
| 已绑定 IO 有普通边 | 选择保留普通连线或保留绑定 |
| 重复端口 | 为 IO 分配不同目标端口 |
| 端口未连接 | 补充真实数据边或删除映射 |
| 覆盖不完整 | 增加 IO 映射覆盖剩余已连接端口 |
| 目标缺失 | 解绑 IO 并重新选择目标 |

---

## 16. 测试方案

### 16.1 后端单元测试

在 `csi-back/tests/service/test_action_compiler.py` 增加：

1. 输入 IO 可绑定零入度目标。
2. 输出 IO 可绑定零出度目标。
3. 输入 IO 不能绑定中间节点。
4. 输出 IO 不能绑定中间节点。
5. 同一目标不能混合输入、输出绑定。
6. 同一目标可绑定多个同方向 IO。
7. 多个同方向 IO 可映射不同端口。
8. 多个同方向 IO 不能映射同一端口。
9. 单个 IO 可映射多个目标端口。
10. 映射端口必须真实参与数据边。
11. 所有已连接可替换端口必须完整覆盖。
12. 已绑定 IO 不能保留普通数据边。
13. 绑定目标不能是 IO 节点。
14. 一个 IO 暴露多个不同类型的相邻 Handle 时拒绝。
15. 节点遍历顺序变化不改变执行计划。
16. 多个入口、多个出口编译结果稳定。
17. 独立运行保留目标节点。
18. 封装运行跳过目标并正确重写。
19. 执行图不存在引用已跳过节点的边。
20. 历史 Revision 加载不触发重新编译。

### 16.2 后端 API 测试

增加：

1. 创建非法绑定蓝图返回明确错误。
2. 更新图结构导致绑定失效时拒绝保存。
3. `/validate` 返回结构化绑定问题。
4. 发布非法蓝图失败。
5. 封装非法蓝图失败。
6. 合法多 IO 绑定可发布并生成多个公开 Handles。
7. 已发布 Revision 不因草稿后续绑定修改而变化。

### 16.3 前端纯函数测试

在 `csi-front/tests/boundary-binding.test.mjs` 增加：

1. 起始、结束和中间节点识别。
2. 单一目标角色推导。
3. 多个同方向 IO 聚合。
4. 混合方向冲突识别。
5. 已占用端口过滤。
6. 绑定模式和普通边冲突。
7. 端口覆盖完整性。
8. 图结构改变后的失效检测。
9. 派生关系线不进入普通数据边。
10. 单一绑定 Handle 可接受方向计算。

### 16.4 前端组件测试

覆盖：

1. 只有符合条件的节点显示绑定 Handle。
2. 节点只显示一个可见 Handle。
3. 多个 IO 绑定后显示正确数量。
4. 输入关系为蓝色，输出关系为紫色。
5. 手动连接触发对话框而不新增数据边。
6. 整卡拖动和 Handle 连接调用同一绑定逻辑。
7. 中间节点显示明确禁用原因。
8. 方向冲突被阻止。
9. 已绑定 IO 无法创建普通数据边。
10. 解绑后恢复普通数据连线能力。
11. 节点尺寸变化后 Handle、边框、关系线不偏移。
12. 侧栏宽度变化后绑定展示不偏移。

### 16.5 端到端场景

1. `Source -> Work -> Sink` 绑定为 `Input -> Work -> Output`。
2. 一个 Source 的两个输出分别绑定两个 Input。
3. 一个 Sink 的两个输入分别绑定两个 Output。
4. 拖动 IO 节点到目标完成绑定。
5. 通过统一 Handle 完成手动绑定。
6. 修改普通边使绑定失效并完成修复。
7. 保存、发布、封装并作为父蓝图节点运行。
8. 独立运行使用原 Source、Sink。
9. 封装运行使用父流程输入、输出。
10. 打开包含历史非法绑定的蓝图并定位错误。

---

## 17. 实施顺序

### 阶段 1：后端规则收紧

1. 抽取全局绑定声明。
2. 实现起始、结束目标校验。
3. 实现目标角色互斥。
4. 实现 IO 模式互斥。
5. 实现端口真实连线和完整覆盖校验。
6. 返回结构化校验问题。
7. 补充编译器和 API 测试。

完成标准：

- 非法图不能创建、更新、发布、封装；
- 合法多 IO 同方向绑定继续工作；
- 当前合法执行计划不发生非预期变化。

### 阶段 2：前端统一派生状态

1. 重构 `boundaryBinding.js`。
2. 建立数据图索引。
3. 建立目标状态聚合。
4. 保存前执行同规则本地校验。
5. 历史非法关系显示错误状态。
6. 补充纯函数测试。

完成标准：

- 拖动前即可判断目标是否合法；
- 图边变化后绑定状态立即更新；
- 前后端对同一图给出一致结论。

### 阶段 3：统一绑定 Handle

1. 新增 `BoundaryBindingAnchor.vue`。
2. 在 `GenericNode.vue` 接入单一可见 Handle。
3. 增加内部方向协议端点。
4. 拦截绑定 `onConnect`。
5. 保留整卡拖动入口。
6. 补充悬停提示和键盘能力。

完成标准：

- 每个节点最多一个可见绑定 Handle；
- Handle 可绑定多个 IO；
- 不生成普通数据边；
- 输入、输出方向均可建立绑定。

### 阶段 4：关系线和布局

1. 派生只读绑定关系线。
2. 增加输入、输出颜色。
3. 增加多绑定数量徽标。
4. 优化 IO 初始定位和关系线布局。
5. 保证用户位置不受节点尺寸、侧栏宽度和视口变化影响。
6. 移除或弱化旧的短尾线展示。

完成标准：

- 绑定关系无需依赖节点重叠即可识别；
- 多个 IO 与同一目标的关系清晰；
- 任何尺寸变化不造成边框或关系线偏移。

### 阶段 5：历史数据审计

1. 实现只读审计。
2. 输出问题统计。
3. 在前端提供问题定位。
4. 验证旧 Revision 不变。
5. 对非法草稿实施阻止新写入策略。

---

## 18. 预计修改文件

### 18.1 前端

- `csi-front/src/views/action/NewActionBlueprint.vue`
- `csi-front/src/utils/action/boundaryBinding.js`
- `csi-front/src/components/action/BoundaryBindingDialog.vue`
- `csi-front/src/components/action/nodes/GenericNode.vue`
- `csi-front/src/components/action/nodes/components/HandleRenderer.vue`
- `csi-front/src/components/action/nodes/components/BoundaryBindingAnchor.vue`（新增）
- `csi-front/tests/boundary-binding.test.mjs`

根据关系线实现方式，可能新增：

- `csi-front/src/components/action/edges/BoundaryBindingEdge.vue`

### 18.2 后端

- `csi-back/app/service/native_nodes/compiler_registry.py`
- `csi-back/app/service/action_compiler.py`
- `csi-back/app/service/blueprint_revision.py`
- `csi-back/app/schemas/action/interface.py`
- `csi-back/app/api/v1/endpoints/action/blueprint.py`
- `csi-back/tests/service/test_action_compiler.py`
- `csi-back/tests/api/test_action_resource_refactor.py`

根据校验复杂度，可能新增：

- `csi-back/app/service/boundary_binding_validator.py`
- `csi-back/scripts/audit_boundary_bindings.py`

---

## 19. 验收标准

### 19.1 交互验收

- [ ] 每个符合条件的非 IO 节点只显示一个绑定 Handle。
- [ ] 一个绑定 Handle 可以绑定多个同方向 IO 节点。
- [ ] 输入、输出不显示为两个独立绑定接口。
- [ ] 输入 IO 可通过 Handle 连接建立绑定。
- [ ] 输出 IO 可通过明确的连接操作建立绑定。
- [ ] 整卡拖动绑定继续可用。
- [ ] 候选节点高亮能区分允许、冲突和不兼容。
- [ ] 中间节点不能建立绑定。
- [ ] 同一目标不能混合输入、输出绑定。
- [ ] 已绑定 IO 不能继续建立普通数据边。
- [ ] 解绑后 IO 恢复独立数据连线能力。

### 19.2 展示验收

- [ ] 输入 IO 使用淡蓝色背景。
- [ ] 输出 IO 使用淡紫色背景。
- [ ] 其他后端原生节点与普通节点使用一致样式。
- [ ] 入口替代目标显示淡蓝色边框。
- [ ] 出口替代目标显示淡紫色边框。
- [ ] 多个绑定关系可以明确区分。
- [ ] 绑定关系线不与普通数据边混淆。
- [ ] 悬停可以看到 IO 名称、关系含义和端口映射。
- [ ] 节点尺寸或侧栏宽度变化不会造成边框、Handle、关系线偏移。
- [ ] 执行状态展示不会导致绑定关系完全不可见。

### 19.3 数据验收

- [ ] 虚拟绑定 Handle 不写入节点定义。
- [ ] 绑定关系线不写入 `graph.edges`。
- [ ] `boundary_binding` 仍是绑定关系唯一权威数据。
- [ ] 多个 IO 通过各自 `boundary_binding` 指向同一目标。
- [ ] 保存请求不包含 `bindingDisplay`、`bindingTargetKinds` 等派生字段。
- [ ] 旧 Revision 内容哈希和执行计划不被修改。

### 19.4 编译验收

- [ ] 独立运行跳过 IO 并执行原目标节点。
- [ ] 封装运行跳过目标并由 IO 正确替换。
- [ ] 多个同方向 IO 可替换同一目标的不同端口。
- [ ] 重复端口占用被拒绝。
- [ ] 输入、输出混合绑定同一目标被拒绝。
- [ ] 中间节点绑定被拒绝。
- [ ] 已绑定 IO 保留普通数据边时被拒绝。
- [ ] 未连接映射端口被拒绝。
- [ ] 端口覆盖不完整被拒绝。
- [ ] 编译结果与节点遍历顺序无关。
- [ ] 重写后不存在悬空边或循环。

---

## 20. 风险和控制

| 风险 | 影响 | 控制方式 |
|---|---|---|
| Vue Flow 单 Handle 方向冲突 | 输出绑定无法从 IO 侧拖动 | 单一视觉层下使用两个内部协议端点，并补充点击连接 |
| 派生关系线被保存 | 污染执行图 | 独立关系集合，保存前再次过滤 |
| 图编辑后绑定失效 | 保存后编译结果异常 | 前端实时校验，后端权威校验 |
| 多 IO 修改顺序影响结果 | 执行计划不确定 | Adapter 声明式收集后统一合并 |
| 历史蓝图不符合新规则 | 无法继续编辑 | 兼容读取、问题定位、不修改旧 Revision |
| 目标端口覆盖不完整 | 下游或上游分支静默丢失 | 保存和发布时强制完整覆盖 |
| 绑定和普通边同时存在 | 数据语义重复 | 两种模式互斥 |
| 用户误以为目标仍执行 | 封装结果与预期不符 | 对话框、Tooltip 和关系摘要明确提示“目标不会执行” |
| 执行边框覆盖绑定边框 | 绑定状态不可见 | 关系线、顶部 Handle 和角标持续展示 |

---

## 21. 后续扩展

### 21.1 端口暴露

如果需要让普通节点继续执行，同时把其真实输入或输出暴露为蓝图接口，应新增独立模型，例如：

```text
interface_exposure
```

该能力不能复用 `boundary_binding`，因为两者执行语义不同：

- `boundary_binding`：替换并跳过目标节点；
- `interface_exposure`：保留目标节点并向其输入或从其输出传输数据。

### 21.2 子图分段

如果需要允许中间节点作为入口、出口并把一张蓝图切成多个片段，应新增：

- 明确的切入点、切出点；
- 片段身份；
- 节点归属；
- 共享节点规则；
- 入口到出口可达性；
- 片段间依赖；
- 单独的发布和调用契约。

在这些语义完成前，不开放中间节点绑定。

### 21.3 节点定义级策略

未来可以让某些普通、后端原生或封装节点显式禁用绑定，但该字段只负责能力收紧，不负责放宽图结构约束。

---

## 22. 最终结论

本次重构采用以下最终原则：

1. 绑定继续表示封装运行时替换目标节点。
2. 每个非 IO 目标节点只显示一个虚拟绑定 Handle。
3. 一个绑定 Handle 可以绑定多个同方向 IO。
4. 输入、输出不拆成两个可见绑定接口。
5. 同一目标禁止混合输入、输出绑定。
6. 第一阶段只允许输入绑定起始节点、输出绑定结束节点。
7. 中间节点绑定留给未来明确的子图分段能力。
8. 绑定关系和普通数据连线完全分离。
9. `boundary_binding` 继续作为唯一持久化事实来源。
10. 前端负责交互和即时反馈，后端负责最终约束。
11. 旧 Revision 保持不变，非法草稿兼容读取但必须修复后才能继续写入。
12. 所有绑定图变更必须声明式收集、整体校验和确定性合并。

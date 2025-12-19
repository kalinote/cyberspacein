# CSI Base Component SDK

CSI 基础组件开发工具包，提供异步和同步组件开发的基础能力。

## 功能特性

- 支持远程模式和本地调试模式
- 提供异步（`AsyncBaseComponent`）和同步（`BaseComponent`）两种版本
- 异步/同步上下文管理器，自动管理资源
- 自动从远程API或本地配置文件加载配置
- 支持进度上报、结果提交、失败上报
- 支持命令行参数和环境变量配置

## 安装

```bash
pip install csi-base-component-sdk
```

或从源码安装：

```bash
pip install -e .
```

## 基本用法

### 异步版本（AsyncBaseComponent）

#### 方式一：使用异步上下文管理器（推荐）

```python
import asyncio
from csi_base_component_sdk import AsyncBaseComponent

async def main():
    async with AsyncBaseComponent() as node:
        # 获取配置
        api_key = node.get_config('api_key')
        timeout = node.get_config('timeout', default=30)
        
        # 获取输入数据
        input_data = node.inputs.get('data')
        
        # 上报进度
        await node.report_progress(50, "处理中...")
        
        # 执行业务逻辑
        result = await process_data(input_data)
        
        # 提交结果
        await node.finish({
            'result': result,
            'status': 'success'
        })

if __name__ == '__main__':
    asyncio.run(main())
```

#### 方式二：手动初始化

```python
import asyncio
from csi_base_component_sdk import AsyncBaseComponent

async def main():
    node = AsyncBaseComponent()
    await node.initialize()
    
    try:
        # 业务逻辑
        result = await process_data()
        await node.finish({'result': result})
    except Exception as e:
        await node.fail(str(e))
    finally:
        await node.close()

if __name__ == '__main__':
    asyncio.run(main())
```

### 同步版本（BaseComponent）

#### 方式一：使用上下文管理器（推荐）

```python
from csi_base_component_sdk import BaseComponent

def main():
    with BaseComponent() as node:
        # 获取配置
        api_key = node.get_config('api_key')
        timeout = node.get_config('timeout', default=30)
        
        # 获取输入数据
        input_data = node.inputs.get('data')
        
        # 上报进度
        node.report_progress(50, "处理中...")
        
        # 执行业务逻辑
        result = process_data(input_data)
        
        # 提交结果
        node.finish({
            'result': result,
            'status': 'success'
        })

if __name__ == '__main__':
    main()
```

#### 方式二：手动初始化

```python
from csi_base_component_sdk import BaseComponent

def main():
    node = BaseComponent()
    node.initialize()
    
    try:
        # 业务逻辑
        result = process_data()
        node.finish({'result': result})
    except Exception as e:
        node.fail(str(e))
    finally:
        node.close()

if __name__ == '__main__':
    main()
```

## 配置方式

### 远程模式

通过命令行参数：

```bash
python your_component.py --action-node-id <节点ID> --api-base-url <API地址>
```

通过环境变量：

```bash
export ACTION_NODE_ID=<节点ID>
export API_BASE_URL=<API地址>
python your_component.py
```

在代码中指定：

**异步版本：**
```python
async with AsyncBaseComponent(
    action_node_id='your-node-id',
    api_base_url='https://api.example.com'
) as node:
    # ...
```

**同步版本：**
```python
with BaseComponent(
    action_node_id='your-node-id',
    api_base_url='https://api.example.com'
) as node:
    # ...
```

### 本地调试模式

通过命令行参数：

```bash
python your_component.py --local-config config.json
```

在代码中指定：

**异步版本：**
```python
async with AsyncBaseComponent(manual_config='config.json') as node:
    # ...
```

**同步版本：**
```python
with BaseComponent(manual_config='config.json') as node:
    # ...
```

本地配置文件格式（`config.json`）：

```json
{
  "config": {
    "api_key": "your-api-key",
    "timeout": 30
  },
  "inputs": {
    "data": "input data"
  },
  "outputs": {}
}
```

## API 文档

### AsyncBaseComponent（异步版本）

#### 构造函数

```python
AsyncBaseComponent(
    action_node_id: str = None,
    api_base_url: str = None,
    manual_config: str = None
)
```

**参数：**
- `action_node_id`: 行动节点ID（远程模式必需）
- `api_base_url`: API基础URL（远程模式必需）
- `manual_config`: 本地配置文件路径（本地调试模式）

**说明：**
- 参数优先级：构造函数参数 > 命令行参数 > 环境变量
- 如果同时提供了 `action_node_id` 和 `api_base_url`，将使用远程模式
- 如果提供了 `manual_config`，将使用本地模式
- 如果都不提供，将以空模式启动（仅用于测试）

#### 属性

- `config: Dict[str, Any]`: 配置字典
- `inputs: Dict[str, Any]`: 输入数据字典
- `outputs: Dict[str, Any]`: 输出数据字典
- `is_remote: bool`: 是否为远程模式

#### 方法

##### `async def initialize()`

初始化组件，从远程API或本地文件加载配置。

**使用场景：**
- 手动初始化模式（不使用上下文管理器时）

##### `async def close()`

关闭 HTTP 会话。

**使用场景：**
- 手动清理资源

##### `get_config(key: str, default: Any = None) -> Any`

获取配置值。

**参数：**
- `key`: 配置键名
- `default`: 默认值（当配置不存在时返回）

**返回值：**
- 配置值。如果配置是引用类型（`type: 'reference'`），返回 URI；如果是值类型，返回 `content`。

**示例：**

```python
api_key = node.get_config('api_key')
timeout = node.get_config('timeout', default=30)
```

##### `async def report_progress(percentage: int, message: str = "")`

上报执行进度。

**参数：**
- `percentage`: 进度百分比（0-100）
- `message`: 进度消息（可选）

**说明：**
- 远程模式：通过心跳接口上报进度，如果收到停止指令会自动退出
- 本地模式：仅输出日志

**示例：**

```python
await node.report_progress(25, "开始处理")
await node.report_progress(50, "处理中...")
await node.report_progress(100, "完成")
```

##### `async def finish(outputs: Dict[str, Any])`

提交成功结果。

**参数：**
- `outputs`: 输出数据字典

**说明：**
- 远程模式：提交到后端API
- 本地模式：输出到日志

**示例：**

```python
await node.finish({
    'result': 'success',
    'data': processed_data,
    'count': len(processed_data)
})
```

##### `async def fail(error_msg: str)`

上报任务失败。

**参数：**
- `error_msg`: 错误消息

**说明：**
- 调用此方法后会退出程序（`sys.exit(1)`）
- 远程模式：上报失败状态到后端
- 本地模式：输出错误日志

**示例：**

```python
try:
    result = await process_data()
except Exception as e:
    await node.fail(f"处理失败: {str(e)}")
```

### BaseComponent（同步版本）

#### 构造函数

```python
BaseComponent(
    action_node_id: str = None,
    api_base_url: str = None,
    manual_config: str = None
)
```

**参数：**
- `action_node_id`: 行动节点ID（远程模式必需）
- `api_base_url`: API基础URL（远程模式必需）
- `manual_config`: 本地配置文件路径（本地调试模式）

**说明：**
- 参数优先级：构造函数参数 > 命令行参数 > 环境变量
- 如果同时提供了 `action_node_id` 和 `api_base_url`，将使用远程模式
- 如果提供了 `manual_config`，将使用本地模式
- 如果都不提供，将以空模式启动（仅用于测试）

#### 属性

- `config: Dict[str, Any]`: 配置字典
- `inputs: Dict[str, Any]`: 输入数据字典
- `outputs: Dict[str, Any]`: 输出数据字典
- `is_remote: bool`: 是否为远程模式

#### 方法

##### `def initialize()`

初始化组件，从远程API或本地文件加载配置。

**使用场景：**
- 手动初始化模式（不使用上下文管理器时）

##### `def close()`

关闭 HTTP 会话。

**使用场景：**
- 手动清理资源

##### `get_config(key: str, default: Any = None) -> Any`

获取配置值。

**参数：**
- `key`: 配置键名
- `default`: 默认值（当配置不存在时返回）

**返回值：**
- 配置值。如果配置是引用类型（`type: 'reference'`），返回 URI；如果是值类型，返回 `content`。

**示例：**

```python
api_key = node.get_config('api_key')
timeout = node.get_config('timeout', default=30)
```

##### `def report_progress(percentage: int, message: str = "")`

上报执行进度。

**参数：**
- `percentage`: 进度百分比（0-100）
- `message`: 进度消息（可选）

**说明：**
- 远程模式：通过心跳接口上报进度，如果收到停止指令会自动退出
- 本地模式：仅输出日志

**示例：**

```python
node.report_progress(25, "开始处理")
node.report_progress(50, "处理中...")
node.report_progress(100, "完成")
```

##### `def finish(outputs: Dict[str, Any])`

提交成功结果。

**参数：**
- `outputs`: 输出数据字典

**说明：**
- 远程模式：提交到后端API
- 本地模式：输出到日志

**示例：**

```python
node.finish({
    'result': 'success',
    'data': processed_data,
    'count': len(processed_data)
})
```

##### `def fail(error_msg: str)`

上报任务失败。

**参数：**
- `error_msg`: 错误消息

**说明：**
- 调用此方法后会退出程序（`sys.exit(1)`）
- 远程模式：上报失败状态到后端
- 本地模式：输出错误日志

**示例：**

```python
try:
    result = process_data()
except Exception as e:
    node.fail(f"处理失败: {str(e)}")
```

## 完整示例

### 异步版本示例

#### 示例1：简单的数据处理组件

```python
import asyncio
from csi_base_component_sdk import AsyncBaseComponent

async def process_data(data):
    """模拟数据处理"""
    await asyncio.sleep(1)
    return [item.upper() for item in data]

async def main():
    async with AsyncBaseComponent() as node:
        await node.report_progress(10, "开始处理")
        
        input_data = node.inputs.get('data', [])
        if not input_data:
            await node.fail("缺少输入数据")
        
        await node.report_progress(30, "处理数据中...")
        result = await process_data(input_data)
        
        await node.report_progress(80, "处理完成")
        
        await node.finish({
            'processed_data': result,
            'count': len(result)
        })

if __name__ == '__main__':
    asyncio.run(main())
```

#### 示例2：带错误处理的组件

```python
import asyncio
from csi_base_component_sdk import AsyncBaseComponent

async def main():
    node = AsyncBaseComponent()
    await node.initialize()
    
    try:
        api_key = node.get_config('api_key')
        if not api_key:
            await node.fail("缺少API密钥配置")
        
        await node.report_progress(20, "连接API...")
        
        # 模拟API调用
        result = await call_external_api(api_key, node.inputs)
        
        await node.report_progress(90, "处理完成")
        await node.finish({'result': result})
        
    except Exception as e:
        await node.fail(f"执行失败: {str(e)}")
    finally:
        await node.close()

async def call_external_api(api_key, inputs):
    await asyncio.sleep(1)
    return {'status': 'ok'}

if __name__ == '__main__':
    asyncio.run(main())
```

### 同步版本示例

#### 示例1：简单的数据处理组件

```python
from csi_base_component_sdk import BaseComponent
import time

def process_data(data):
    """模拟数据处理"""
    time.sleep(1)
    return [item.upper() for item in data]

def main():
    with BaseComponent() as node:
        node.report_progress(10, "开始处理")
        
        input_data = node.inputs.get('data', [])
        if not input_data:
            node.fail("缺少输入数据")
        
        node.report_progress(30, "处理数据中...")
        result = process_data(input_data)
        
        node.report_progress(80, "处理完成")
        
        node.finish({
            'processed_data': result,
            'count': len(result)
        })

if __name__ == '__main__':
    main()
```

#### 示例2：带错误处理的组件

```python
from csi_base_component_sdk import BaseComponent
import time

def main():
    node = BaseComponent()
    node.initialize()
    
    try:
        api_key = node.get_config('api_key')
        if not api_key:
            node.fail("缺少API密钥配置")
        
        node.report_progress(20, "连接API...")
        
        # 模拟API调用
        result = call_external_api(api_key, node.inputs)
        
        node.report_progress(90, "处理完成")
        node.finish({'result': result})
        
    except Exception as e:
        node.fail(f"执行失败: {str(e)}")
    finally:
        node.close()

def call_external_api(api_key, inputs):
    time.sleep(1)
    return {'status': 'ok'}

if __name__ == '__main__':
    main()
```

## 注意事项

1. **上下文管理器**：
   - 异步版本：推荐使用 `async with` 语句，自动管理资源
   - 同步版本：推荐使用 `with` 语句，自动管理资源
2. **版本选择**：
   - 如果项目使用异步框架（如 FastAPI、aiohttp），使用 `AsyncBaseComponent`
   - 如果项目使用同步框架（如 Flask、requests），使用 `BaseComponent`
   - 两个版本的 API 接口完全一致，只是异步版本的方法需要 `await`
3. **进度上报**：在远程模式下，进度上报可能会收到停止指令，程序会自动退出
4. **错误处理**：使用 `fail()` 方法上报失败，程序会自动退出
5. **配置优先级**：构造函数参数 > 命令行参数 > 环境变量
6. **本地调试**：使用 `--local-config` 参数可以方便地进行本地调试

## 命令行参数

- `--action-node-id`: 行动节点ID
- `--api-base-url`: API基础URL
- `--local-config`: 本地调试配置文件路径

## 环境变量

- `ACTION_NODE_ID`: 行动节点ID
- `API_BASE_URL`: API基础URL

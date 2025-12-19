# CSI Base Component SDK

CSI 基本组件开发工具包，提供异步组件开发的基础功能。

## 功能特性

- 支持远程和本地两种运行模式
- 异步初始化配置（从远程API或本地文件）
- 自动处理输入数据的 Value/Reference 结构
- 进度上报和心跳机制
- 结果提交和错误处理
- 支持异步上下文管理器

## 安装

```bash
pip install -r requirements.txt
```

或使用 setuptools 安装：

```bash
python setup.py install
```

## 依赖

- Python >= 3.7
- aiohttp

## 使用方法

### 基本用法

```python
import asyncio
from csi_base_component_sdk import AsyncBaseComponent

async def main():
    async with AsyncBaseComponent() as node:
        # 获取输入数据
        input_value = node.get_input('key', default='default_value')
        
        # 上报进度
        await node.report_progress(50, "处理中...")
        
        # 提交结果
        await node.finish({
            'output_key': 'output_value'
        })

asyncio.run(main())
```

### 远程模式

通过环境变量或命令行参数配置：

```bash
export ACTION_NODE_ID=your_node_id
export API_BASE_URL=https://api.example.com
python your_script.py
```

或使用命令行参数：

```bash
python your_script.py --action-node-id your_node_id --api-base-url https://api.example.com
```

### 本地调试模式

使用本地配置文件进行调试：

```bash
python your_script.py --local-config config.json
```

配置文件格式：

```json
{
  "inputs": {
    "key": "value"
  },
  "config": {
    "setting": "value"
  }
}
```

### 编程方式初始化

```python
async with AsyncBaseComponent(
    action_node_id='node_id',
    api_base_url='https://api.example.com'
) as node:
    # 使用 node...
    pass
```

## API 参考

### AsyncBaseComponent

#### 方法

- `get_input(key, default=None)`: 获取输入数据
- `report_progress(percentage, message="")`: 上报进度
- `finish(outputs)`: 提交成功结果
- `fail(error_msg)`: 上报失败状态

## 许可证

MIT License


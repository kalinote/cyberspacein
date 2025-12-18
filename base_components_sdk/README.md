# Base Components SDK

异步Flow Node SDK，用于与后端API交互的Python包。

## 功能特性

- 支持异步上下文管理器
- 支持远程模式和本地调试模式
- 自动处理输入数据的Value/Reference结构
- 支持进度上报和结果提交
- 支持任务失败上报

## 安装

```bash
pip install base-components-sdk
```

## 使用方法

```python
import asyncio
from base_components_sdk import AsyncFlowNode

async def main():
    async with AsyncFlowNode(context_id="your_context_id", api_host="http://api.example.com") as node:
        # 获取输入
        input_data = node.get_input("key", default="default_value")
        
        # 上报进度
        await node.report_progress(50, "处理中...")
        
        # 提交结果
        await node.finish({"output": "result"})

if __name__ == "__main__":
    asyncio.run(main())
```

## 开发

### 构建wheel包

```bash
python setup.py bdist_wheel
```

### 安装开发版本

```bash
pip install -e .
```

## 许可证

MIT License


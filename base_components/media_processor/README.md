# 媒体资源处理器接入说明

本组件接收业务数据中的媒体清单，独立完成下载、内容哈希去重、COS/S3 归档及逐项状态记录。入口是 `csi-component run main:run`，无需导入或部署其他基础组件。单条运行配置见 [test_config.json](test_config.json)，队列配置见 [test_queue_config.json](test_queue_config.json)，存储配置见 [.env.example](.env.example)。

## 1. 适用场景与组件选择

本组件适用于上游已经提取媒体地址、需要统一下载归档并保留处理状态的场景。按上游输出结构和所需结果选择组件：

| 爬虫输出和所需结果 | 组件及配置 |
| --- | --- |
| 有 HTML 正文，需要提取纯文本 | `html_analyze`：`process_fields=raw_content`、`clean_content=true` |
| 需要净化 HTML，并将 HTML 中的媒体地址替换为归档地址 | `html_analyze`：`safe_raw_content=true`、`media_localization=true`；存在相对链接时配置 `base_url_field=url` |
| 正文已是纯文本，图片、视频等已提取为独立清单 | `media_processor`；提供完整媒体清单 |
| 只需要归档一组明确的媒体或附件地址 | `media_processor`；业务对象中提供媒体清单即可 |
| 只有平台原始 JSON，尚未解析正文及媒体地址 | 先在爬虫中完成平台字段适配，再选择对应组件；原始 JSON 本身不构成媒体清单 |

`html_analyze` 的 `media_localization` 位于 `safe_raw_content` 处理分支内，只打开前者不会执行媒体本地化。处理后的 HTML 写入 `safe_raw_content`。

混合数据可根据目标组装独立节点：

- 需要替换 HTML 内媒体链接时，由 `html_analyze` 处理该部分；独立于 HTML 的附件可另交给 `media_processor`。应明确各节点清单，避免重复下载同一媒体。
- 如果需要统一的媒体状态清单，可让 `html_analyze` 仅提取文本和净化 HTML（`media_localization=false`），再由 `media_processor` 处理爬虫准备的完整媒体清单。此时 HTML 内链接仍是源地址，展示端需要依据媒体结果自行关联。

两个组件可通过业务数据连接，各自保持独立运行。

## 2. 输入数据规范

### 每条业务数据

1. 一条业务记录对应一个可 JSON 序列化的对象，媒体项放在该对象内部。队列消息反序列化一次后应得到对象，不能是再次序列化的 JSON 字符串或媒体数组。
2. 接入完整内容链路时，爬虫或前置节点应已经提取完整 `clean_content`，并保留原始 `raw_content`。本组件原样保留这些字段，不提取正文、不生成安全 HTML，也不检查正文是否完整。
3. `platform`、`entity_type`、`source_id`、`uuid`、来源页 `url`、作者、时间等业务字段继续遵守平台及下游存储契约。本组件会保留它们，但不会补齐这些字段或校验实体类型。
4. 需要归档的图片、视频、音频、附件和封面必须写入媒体清单；仅放在 `raw_content`、`cover_image`、平台私有字段或嵌套对象中不会触发处理。
5. 确认没有媒体时可使用空数组。遗漏清单也会按无媒体透传，不能将“尚未提取媒体”当成“确实没有媒体”。

### 媒体清单的两种形式

**简单清单：**适用于只需要下载地址的场景。

```json
{
  "files_urls": [
    "https://example.com/image.jpg",
    "https://example.com/video.mp4"
  ]
}
```

**结构化清单：**需要保留媒体类型、封面角色、尺寸或媒体标识时使用。

```json
{
  "source_id": "example-record",
  "url": "https://example.com/records/1",
  "clean_content": "示例业务记录的完整正文。",
  "raw_content": "{\"text\":\"示例业务记录的完整正文。\",\"media_ids\":[\"image-1\",\"video-1\"]}",
  "media_resources": [
    {
      "source_url": "https://example.com/image.jpg",
      "media_id": "image-1",
      "type": "image",
      "role": "content",
      "width": 1200,
      "height": 800
    },
    {
      "source_url": "https://example.com/video.mp4",
      "media_id": "video-1",
      "type": "video",
      "role": "content"
    },
    {
      "source_url": "https://example.com/poster.jpg",
      "media_id": "video-1",
      "type": "image",
      "role": "poster"
    }
  ]
}
```

以上地址和原始 JSON 均为结构示例，需要替换为实际采集数据。

| 字段 | 爬虫要求 |
| --- | --- |
| `source_url` | 结构化媒体项的必填字段，必须是非空字符串；提供绝对 HTTP/HTTPS 文件直链 |
| `type` | 可选元数据，建议使用 `image`、`video`、`audio`、`file`；当前组件保留此值，不据此选择解析器或判断实际文件格式 |
| `role` | 可选元数据，建议使用 `content`、`cover`、`poster`，用于区分正文资源、封面、视频预览图 |
| `media_id` | 可选的平台媒体标识；视频和对应封面可使用相同标识，由角色区分 |
| `width`、`height`、其他元数据 | 可选，使用可 JSON 序列化的值；组件原样保留 |

`media_resources` 中也兼容直接使用 URL 字符串。两种清单的优先级固定：

- `media_resources` 存在且不为 `null` 时，作为完整清单使用，**不会与 `files_urls` 合并**。
- `media_resources=[]` 明确表示清单为空，即使 `files_urls` 非空也不会回退。
- `media_resources` 缺失或为 `null` 时，才读取 `files_urls`；两者均缺失或为 `null` 时按无媒体处理。

首次采集仅需提供源地址与平台元数据。`stored_url`、`storage_key`、`sha256`、`size`、`content_type`、`status`、`attempts`、`error` 是组件生成的结果字段，不应由爬虫伪造成功状态。

## 3. 爬虫的适配职责

- **媒体直链与相对路径：**提供返回完整文件内容的地址。相对地址由爬虫补全。贴文页面、预览页面、播放器页面、返回媒体描述 JSON 的接口、`blob:`、`data:` 和 `file:` 地址不应作为下载目标；`media_processor` 不会从这些内容中继续寻找媒体。
- **视频版本：**由爬虫在平台返回的版本列表中选择需要归档的清晰度或码率，提供可直接下载的 MP4 等文件地址。视频封面另列为图片项，不能用封面代替视频。
- **签名与登录态：**由爬虫或任务配置保证地址在处理时仍有效。保留签名 URL 的完整查询参数；本组件不刷新签名、登录态或平台接口令牌。
- **下载鉴权：**通过本节点的 `download_headers` 配置 Cookie、Referer 等所需请求头，通过 `proxy_url` 或 `DOWNLOAD_PROXY` 配置代理。默认 Referer 来自业务数据的 `url`，可由节点请求头覆盖。爬虫节点的 Cookie、请求头和代理不会自动继承到本节点。
- **不同鉴权要求：**当前请求头和代理作用于整个节点，不从单项媒体元数据读取 `headers` 或 Cookie。需要不同账号或不同下载请求头的数据应连接到分别配置的处理节点；凭据不要写入会被透传和存储的媒体元数据。
- **分片或受保护媒体：**HLS/DASH 清单会返回 `skipped` 与 `unsupported_stream`，本组件没有分片合并、DRM 解密或浏览器下载能力。需要此类内容时应由独立获取流程产出可下载文件，再交给本组件归档。

同一条数据中的相同源地址共享一次处理结果，媒体条目的顺序及各自元数据仍保留；归档对象按内容哈希定位。默认最多处理 100 个不同源地址，单文件限制 50M，单条数据累计读取限制 200M，累计限制包括失败重试读取的字节。600 秒为软时间预算，阻塞请求还受连接和读取超时约束。

## 4. 接入步骤与验收

接入时，在爬虫构造每条业务记录的阶段完成以下适配：

1. 按业务要求完成正文和元数据提取，将原始数据保留在相应字段中。
2. 从响应或页面结构中提取图片、视频、音频、附件及封面，补全相对地址并选择可下载的视频版本。
3. 选择 `files_urls` 或 `media_resources`，将需要归档的全部资源写入同一业务记录；无媒体时明确提供空数组。
4. 若使用 Scrapy Item，在所用 Item 中声明实际使用的清单字段，例如 `files_urls = scrapy.Field()` 或 `media_resources = scrapy.Field()`；普通字典输出直接携带同名数组。
5. 将上游业务数据的 REFERENCE 输出接口连接本节点的 `data_in`，本节点的 `data_out` 再连接下游存储或其他处理节点。
6. 配置本节点的对象存储环境变量，以及下载所需的请求头、代理、大小限制和失败策略。

验收时至少覆盖无媒体、全部成功和部分失败三种数据，检查清单是否完整、成功项是否得到归档地址、失败项是否保留源地址，以及正文和业务元数据是否保持输入值。有媒体的记录输出为 `empty` 时，应检查上游是否遗漏清单或被显式空的 `media_resources` 覆盖。

## 5. 输出与下游接入

| 输出字段 | 含义 |
| --- | --- |
| 原业务字段 | `clean_content`、`raw_content`、来源、作者、关系及指标等保持输入值 |
| `media_resources` | 每项包含原元数据和处理结果；`source_url` 保留源地址，`stored_url` 为成功归档地址 |
| 逐项 `status` | `stored` 为成功，`failed` 为失败，`skipped` 为数量限制或暂不支持等导致的跳过 |
| 逐项 `error` | 成功为 `null`，否则为 `{code, message, retryable}`；可供后续筛选和重试 |
| `files_urls` | 去重后的字符串数组；成功项使用归档地址，失败或跳过项保留源地址 |
| `media_summary` | `status` 为 `empty`、`complete`、`partial` 或 `failed`；同时记录 `total`、`stored`、`failed`、`skipped`，计数基于媒体条目 |

默认 `failure_policy=continue` 会传递包含失败明细的数据；需要全部媒体归档成功时配置 `failure_policy=fail`。单项可重试错误按 `max_retries` 有限重试；输入结构、配置或队列传输错误会终止组件，不在组件内无限重入队。队列模式在全部下游发送成功后才确认输入消息，EOS/ABORT 由 SDK 管理。

下游存储需要接受并保存所需的媒体结果字段及业务实体类型。展示端需要正文内媒体关联时，可依据媒体标识、角色及归档地址处理；本组件不会改写 `raw_content` 或 `safe_raw_content` 中的 URL。

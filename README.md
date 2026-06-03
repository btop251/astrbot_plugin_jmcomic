# astrbot_plugin_jmcomic

![微信图片_20260508142304_413_22](./assets/微信图片_20260508142304_413_22.jpg)

基于 [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) 封装的 AstrBot 插件，优先面向 QQ（NapCat / OneBot）场景设计。

## 默认行为

- 默认下载格式：`pdf`
- 默认回传方式：下载完成后直接上传回当前平台
- 默认缓存策略：仅保留最近 `3` 次下载缓存
- 默认安全策略：只有 `/jm下载整本` 会触发整本下载，其他下载命令都按章节 `photo_id` 下载
- 默认详情展示：`/jmalbum` 以聊天记录格式返回封面节点和文字详情节点
- 默认封面策略：封面默认使用 URL；含封面的合并转发失败时会自动降级为纯文字详情

## 快速开始

### 1. 安装插件

将插件目录放入 AstrBot 插件目录：

```text
data/plugins/astrbot_plugin_jmcomic/
```

然后重启 AstrBot 即可。

也可以直接在 AstrBot 面板中通过 GitHub 地址安装：

```text
https://github.com/btop251/astrbot_plugin_jmcomic
```

### 2. 依赖说明

插件依赖：

```text
jmcomic==2.6.18
```

AstrBot 在加载插件时会自动读取 `requirements.txt` 并安装缺失依赖。

如果你是在 Docker 中部署，通常建议：

- `jm_project_path` 留空
- 直接让容器通过 `requirements.txt` 安装 `jmcomic`

## 推荐使用流程

普通用户建议先从本子详情进入，再按章节下载：

```text
/jmalbum 350234
/jm章节列表 350234 2
/jm章节 350234 11
/jm下载 pdf 438516
```

如果确认要下载整本，再使用显式整本命令：

```text
/jm下载整本 pdf 350234
```

这样可以避免在不确定是否为长篇连载时误把整本挂到后台下载。普通用户只要记住：`album_id` 用来查本子和整本下载，`photo_id` 用来下载具体章节。

## 常用命令

搜索：

```text
/jmsearch 350234
/jmsearch MANA
/jmsearch +中文 -全彩
```

浏览：

```text
/jmalbum 350234
/jmalbum 350234 2
/jm章节列表 350234
/jm章节列表 350234 2
/jm章节 350234 11
/jmphoto 438516
/jmrank month
```

下载：

```text
/jm下载 438516
/jm下载章节 438516
/jm下载章节 pdf 438516
/jm下载整本 pdf 350234
```

任务与配置：

```text
/jm任务
/jm任务详情 task_xxx
/jm停止 task_xxx
/jm配置
/jm帮助
```

## 命令说明

| 命令 | 说明 | 示例 |
|---|---|---|
| `/jmsearch <关键词或车号>` | 最宽松的搜索入口，支持车号、标题关键词与筛选符号 | `/jmsearch 350234` |
| `/jmalbum <album_id> [页码]` | 查询本子详情，以聊天记录格式返回文字详情、封面和指定页章节列表 | `/jmalbum 350234 2` |
| `/jm章节列表 <album_id> [页码]` | 分页查看连载本章节，显示每章 `photo_id` | `/jm章节列表 350234 2` |
| `/jm章节 <album_id> <章节序号>` | 按序号查看章节，并给出单章下载命令 | `/jm章节 350234 11` |
| `/jmphoto <photo_id>` | 已知 `photo_id` 时查询具体章节详情 | `/jmphoto 438516` |
| `/jmrank <month\|week\|day>` | 查看排行 | `/jmrank month` |
| `/jm下载 [格式] <photo_id>` | 章节下载入口，等价于 `/jm下载章节`，不会下载整本 | `/jm下载 pdf 438516` |
| `/jm下载章节 [格式] <photo_id>` | 明确下载单章节并自动上传回当前平台 | `/jm下载章节 pdf 438516` |
| `/jm下载整本 [格式] <album_id>` | 唯一整本下载入口，自动上传回当前平台 | `/jm下载整本 pdf 350234` |
| `/jm任务` | 查看最近任务列表 | `/jm任务` |
| `/jm任务详情 <task_id>` | 查看单个任务的详细状态、上传状态、错误信息等 | `/jm任务详情 task_xxx` |
| `/jm停止 <task_id>` | 停止排队任务；运行中任务会请求软停止并跳过后续上传 | `/jm停止 task_xxx` |
| `/jm配置` | 查看当前生效的关键配置摘要 | `/jm配置` |
| `/jm帮助` | 查看插件帮助 | `/jm帮助` |

## 下载命令补充说明

`/jm下载`、`/jm下载章节` 和 `/jm下载整本` 支持以下格式：

- `pdf`
- `png`
- `jpg`
- `原图`

例如：

```text
/jm下载 pdf 438516
/jm下载 png 438516
/jm下载章节 pdf 438516
/jm下载整本 pdf 350234
/jm下载整本 原图 350234
```

如果省略格式参数，则默认使用：

```text
pdf
```

### 关于 `/jm下载`

`/jm下载` 现在固定为章节下载入口：

- 参数按 `photo_id` 处理
- 行为与 `/jm下载章节` 等价
- 不会检查本子章节数
- 不会触发整本下载

如果你手上只有 `album_id`，请先用 `/jmalbum <album_id>` 或 `/jm章节 <album_id> <序号>` 找到章节 `photo_id`。如果你确认要下载整本，请使用：

```text
/jm下载整本 pdf <album_id>
```

## `jmalbum` 与 `jmphoto` 的区别

`jmalbum` 是普通用户的主入口，用 `album_id` 查询本子。它会用聊天记录格式展示封面、标题、作者、标签、章节列表、章节 `photo_id` 和下载提示。默认封面使用 URL，并放在文字详情节点上方；如果含封面的合并转发发送失败，插件会自动重发纯文字聊天记录，保证详情文本尽量正常回显。

`jmphoto` 是章节直查入口，用 `photo_id` 查询具体章节。它会显示所属本子、标题、图片数、章节序号和单章下载命令。

两者会在单章节本上有一定信息重叠，但使用目的不同：普通用户优先用 `jmalbum` 找章节，已知章节 ID 时再用 `jmphoto` 或直接 `/jm下载`。这样可以减少命令选择成本。

## 下载与回传机制

本插件不是“只下载到本地”的模式，而是：

1. 先下载到插件缓存目录
2. 生成目标输出
3. 自动上传回当前聊天平台
4. 本地仅保留最近 3 次缓存

因此从使用者视角来看，下载命令更接近于：

- 下载并回传

而不是：

- 仅下载到本地磁盘

## 任务停止说明

`/jm停止 <task_id>` 是保守的软停止：

- 排队中的任务会直接取消
- 已经运行中的任务会记录停止请求
- 如果底层下载已经开始，插件会等待当前下载函数返回后跳过后续上传

这不是强制杀线程，因此不保证已经开始的底层下载立即停止。最重要的保护已经改成命令语义固定：除了 `/jm下载整本`，其他下载命令不会触发整本下载。

## 缓存策略

默认缓存策略如下：

- 仅保留最近 `3` 次下载任务缓存
- 更早的缓存会被自动清理

这样做的目的：

- 避免本地空间占用持续增长
- 上传失败时仍保留短期缓存，方便排查
- 在自动清理与可恢复性之间保持平衡

## 配置说明

插件配置按用途划分为以下几个分组：

- `basic`
- `network`
- `auth`
- `download`
- `cache`
- `permission`
- `advanced`

大多数用户只需要先关注下面几项。

### basic

| 配置项 | 说明 | 建议 |
|---|---|---|
| `default_download_format` | 默认下载格式 | 建议保持 `pdf` |
| `search_default_limit` | 搜索默认返回条数 | 默认即可 |
| `album_chapter_page_size` | 本子详情和章节列表每页显示多少章 | 默认 `10` |
| `cover_send_mode` | `jmalbum` 封面发送模式，可选 `url`、`download`、`none`；默认使用 URL，失败时降级为纯文字详情 | 默认 `url` |
| `image_batch_size` | 图片模式回传时，每条消息最多发几张图 | 默认即可 |
| `pdf_merge_batch_size` | PDF 合成时，每批最多处理多少张图片 | 默认 `20`，4核4G 建议先保持默认 |
| `jm_project_path` | 本地 JM 源码路径 | Docker 环境通常留空 |

### network

| 配置项 | 说明 | 建议 |
|---|---|---|
| `client_impl` | JM 客户端实现 | 推荐 `api` |
| `retry_times` | 请求失败重试次数 | 默认即可 |
| `proxy` | 代理设置 | 无代理可保持 `system` 或改 `none` |

### auth

| 配置项 | 说明 | 建议 |
|---|---|---|
| `cookies_avs` | JM 的 AVS cookie | 需要受限内容时再配 |
| `username` | JM 用户名 | 可选 |
| `password` | JM 密码 | 可选 |

### download

| 配置项 | 说明 | 建议 |
|---|---|---|
| `download_base_dir` | 缓存目录 | 留空即可 |
| `dir_rule` | 下载目录规则 | 默认即可 |
| `normalize_zh` | 中文目录归一化 | 按需开启 |
| `download_cache` | 是否跳过重复下载 | 建议开启 |
| `decode_image` | 是否解码还原图片 | 建议开启 |
| `thread_image` | 单章节图片并发数 | 默认即可 |
| `thread_photo` | 单本子章节并发数 | 默认即可 |

### cache

| 配置项 | 说明 | 建议 |
|---|---|---|
| `cache_keep_last` | 保留最近几次下载缓存 | 默认 `3` |

### permission

| 配置项 | 说明 | 建议 |
|---|---|---|
| `allow_group_read` | 是否允许群聊查询 | 建议开启 |
| `allow_private_read` | 是否允许私聊查询 | 建议开启 |
| `allow_group_download` | 是否允许群聊下载 | 建议按需开启 |
| `download_admin_only` | 下载是否仅管理员可用 | 建议开启 |

### advanced

| 配置项 | 说明 | 建议 |
|---|---|---|
| `max_concurrent_tasks` | 后台任务最大并发数 | 默认即可 |
| `task_history_limit` | 任务历史保留数量 | 默认即可 |
| `enable_task_cancel` | 是否启用 `/jm停止` | 默认开启 |
| `enable_jm_log` | 是否启用 jmcomic 内部日志 | 一般关闭 |

## 当前版本重点

当前版本重点完成：

- `jmalbum` 默认使用聊天记录格式，封面节点在上，文字详情节点在下，失败时降级为纯文字详情
- 支持 `/jm章节列表` 和 `/jm章节`
- `/jm下载` 固定为章节下载入口，不再触发整本下载
- `/jm下载整本` 是唯一整本下载入口
- 增加软停止命令 `/jm停止`
- 下载后自动上传到平台
- 默认 PDF 输出
- 最近三次缓存保留
- 更清晰的配置分组

后续可以继续扩展：

- 收藏夹导出
- 长图输出
- 压缩包输出
- 上传失败后的手动重试命令
- 更彻底的协作式下载中断

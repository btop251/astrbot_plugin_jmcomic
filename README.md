# astrbot_plugin_jmcomic

基于 [JMComic-Crawler-Python](https://github.com/hect0x7/JMComic-Crawler-Python) 封装的 AstrBot 插件，优先面向 QQ（NapCat / OneBot）场景设计。

这个插件的目标很明确：

- 用简短命令快速搜索 JM 内容
- 下载完成后直接上传回 AstrBot 当前连接的平台
- 本地仅保留最近 3 次下载缓存，避免长期堆积文件

## 默认行为

- 默认下载格式：`pdf`
- 默认回传方式：下载完成后直接上传回当前平台
- 默认缓存策略：仅保留最近 `3` 次下载缓存

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

### 3. 最常用命令

搜索：

```text
/jmsearch 350234
/jmsearch MANA
/jmsearch +中文 -全彩
```

详情：

```text
/jmalbum 350234
/jmphoto 438516
/jmrank month
```

下载：

```text
/jm下载 350234
/jm下载 pdf 350234
/jm下载 png 350234
/jm下载章节 438516
/jm下载章节 pdf 438516
```

任务与配置：

```text
/jm任务
/jm任务详情 task_xxx
/jm配置
/jm帮助
```

## 命令说明

| 命令 | 说明 | 示例 |
|---|---|---|
| `/jmsearch <关键词或车号>` | 最宽松的搜索入口，支持车号、标题关键词与带筛选符号的关键词 | `/jmsearch 350234` |
| `/jmalbum <album_id>` | 查询本子详情 | `/jmalbum 350234` |
| `/jmphoto <photo_id>` | 查询章节详情 | `/jmphoto 438516` |
| `/jmrank <month\|week\|day>` | 查看排行 | `/jmrank month` |
| `/jm下载 [格式] <album_id>` | 下载整本并自动上传回当前平台；不写格式时默认使用 `pdf` | `/jm下载 350234` |
| `/jm下载章节 [格式] <photo_id>` | 下载单章节并自动上传回当前平台；不写格式时默认使用 `pdf` | `/jm下载章节 438516` |
| `/jm任务` | 查看最近任务列表 | `/jm任务` |
| `/jm任务详情 <task_id>` | 查看单个任务的详细状态、上传状态、错误信息等 | `/jm任务详情 task_xxx` |
| `/jm配置` | 查看当前生效的关键配置摘要 | `/jm配置` |
| `/jm帮助` | 查看插件帮助 | `/jm帮助` |

### 下载命令补充说明

`/jm下载` 和 `/jm下载章节` 支持以下格式：

- `pdf`
- `png`
- `jpg`
- `原图`

例如：

```text
/jm下载 pdf 350234
/jm下载 png 350234
/jm下载 原图 350234
/jm下载章节 pdf 438516
```

如果省略格式参数，则默认使用：

```text
pdf
```

## 下载与回传机制

本插件不是“只下载到本地”的模式，而是：

1. 先下载到插件缓存目录
2. 生成目标输出
3. 自动上传回当前聊天平台
4. 本地仅保留最近 3 次缓存

因此从使用者视角来看，`/jm下载` 更接近于：

- 下载并回传

而不是：

- 仅下载到本地磁盘

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
| `image_batch_size` | 图片模式回传时，每条消息最多发几张图 | 默认即可 |
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
| `enable_jm_log` | 是否启用 jmcomic 内部日志 | 一般关闭 |

## 当前版本重点

当前版本重点完成：

- 更适合聊天场景的命令设计
- 下载后自动上传到平台
- 默认 PDF 输出
- 最近三次缓存保留
- 更清晰的配置分组

后续可以继续扩展：

- 收藏夹导出
- 长图输出
- 压缩包输出
- 上传失败后的手动重试命令

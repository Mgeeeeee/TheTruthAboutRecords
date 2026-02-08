# 更新 SOP（每周新增回答）

目标：把新增的 `WeekXX` 内容和配图接入网页，并把配图转成 WebP 来降低加载体积。

## 项目里关键文件

- `source/`：每周原文（`source/WeekXX丨标题.md`）
- `assets/`：配图资源（周封面在根目录，正文插图可放 `assets/其他图/`）
- `articles.json`：网页读取的数据源（包含每周的 `week/title/question/content/image`）
- `index.html`：页面本体，内嵌了一份 `articles-data` JSON（用于 `file://` 打开时也能读到数据）

## 先决条件（首次配置）

1. 安装 WebP 工具（提供 `cwebp`）

```bash
brew install webp
```

2. 确认可用

```bash
cwebp -version
python3 --version
```

## 每次更新流程（推荐：脚本一键）

1. 准备文件

- 新增/更新 `source/WeekXX丨标题.md`
- 放入封面图 `assets/WeekXX丨标题.png` 或 `assets/WeekXX丨标题.jpg`（脚本会自动生成同名 `.webp`）
- 如果正文有插图，放到 `assets/其他图/`，并在正文用 `![alt](./assets/其他图/xxx.png)` 引用（脚本也会转 `.webp` 并替换链接）

2. `source/*.md` 的最小格式约定

- 问题必须用引用块：以 `>` 开头的连续行（脚本会读取第一段引用块作为 `question`）
- 正文从第一条 `---` 分隔线之后开始（脚本会把其后的内容作为 `content`）
- 封面图可用两种写法之一（可选）

```md
![WeekXX丨标题](./assets/WeekXX丨标题.png)
```

```md
![[WeekXX丨标题.png]]
```

3. 运行脚本

```bash
python3 scripts/add_week.py "source/WeekXX丨标题.md"
```

4. 检查改动

```bash
git status -sb
rg -n "\"completed\": " articles.json
```

5. 本地预览（可选）

```bash
python3 -m http.server 8080
```

然后浏览器打开 `http://localhost:8080/index.html`。

6. 提交并推送

```bash
git add -A
git commit -m "新增 WeekXX 标题"
git push
```

## 手动流程（不推荐，但可用）

1. 用命令把封面图转 WebP（示例）

```bash
cwebp -q 82 -m 6 -mt -metadata none "assets/WeekXX丨标题.png" -o "assets/WeekXX丨标题.webp"
```

2. 更新 `articles.json`

- 新增该周对象（或替换同 `week` 的对象）
- `image` 指向 `./assets/WeekXX丨标题.webp`
- `completed` 改为当前 `articles` 条目数量

3. 同步 `index.html` 的内嵌数据

- `index.html` 内 `<script id="articles-data" type="application/json">...</script>` 需要和 `articles.json` 内容一致
- 建议直接运行脚本来同步，避免手动编辑出错

## 常见问题排查

- `cwebp: command not found`

```bash
brew install webp
```

- 页面显示图片 404

```bash
rg -n "WeekXX丨标题" articles.json
ls "assets/WeekXX丨标题.webp"
```

- `index.html` 打开后提示无法加载数据

- 用本地服务器打开（推荐），或确认 `index.html` 内嵌 `articles-data` 已更新


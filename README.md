# 布丁小窝

基于 Astro 的个人博客，发布在 https://cpudding.github.io/ 。全部页面静态生成，归档、标签、数学公式和全文搜索均不需要后端。

## 本地使用

项目在 `site/`，使用 Node.js 24.22.2（见 `site/.nvmrc`）：

```sh
cd site
nvm use
npm ci
npm run dev
```

浏览器打开终端输出的地址。已配置 nvm 自动加载的终端无需反复 `source ~/.zshrc`。

Astro 7 的开发服务可能在后台运行；用 `npm run stop` 停止，再运行 `npm run dev`。直接输入 `astro` 不会找到项目内的 CLI，请使用 npm 脚本。

发布前检查：

```sh
npm run check
TZ=UTC npm run build
npm test
npm run preview
```

`npm test` 使用 Python 3 标准库检查构建结果，先执行 build。它验证旧文章地址、真实日期、27 段原代码、数学渲染、内部链接与锚点、RSS、站点地图和搜索索引。Python 3 已预装在 GitHub Actions 的 Ubuntu runner 中。

## 写文章

文章放在 `site/src/content/blog/`，Markdown 示例：

```yaml
---
title: "文章标题"
description: "文章摘要"
pubDate: "2026-11-06T10:00:00+08:00"
permalink: "/2026/11/06/文章标题/"
tags: ["笔记"]
---
```

需要记录实质性更新时增加 `updatedDate`。日期必须使用真实的时间和时区；迁移后的四篇旧文仍保留原发布日期与更新时间。`permalink` 决定发布地址，修改文件名不改变地址，请勿随意修改已经公开的 permalink。

使用 `$...$` 和 `$$...$$` 写公式。构建时 MathJax 生成 SVG，无需加载外部公式脚本。代码围栏可标记 `cpp` 等语言，Shiki 在构建时高亮。首页、归档、标签、RSS 和搜索索引随内容自动更新。

## GitHub Pages 发布

源码分支为 `astro-source`，旧站保存在 `hexo-live-before-astro`；`main` 保留迁移前状态。

首次设置：

1. 仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
2. 仓库 **Settings → General → Default branch** 选择 **astro-source**，使手动发布入口可用。
3. 若自行设置过 `github-pages` 环境的分支限制，在 **Settings → Environments → github-pages** 中允许 `astro-source`；默认无限制即可。

以后提交并推送 `astro-source`，`.github/workflows/deploy.yml` 会安装锁定依赖、检查、构建、验收并部署。检查不通过不会执行新部署。无需上传个人 Token 或 SSH 私钥。

在 **Actions → Deploy blog** 查看运行结果；也可点 **Run workflow**，分支选择 `astro-source`、version 选择 `astro`，手动发布。`/build-info.json` 的 revision 对应线上构建的 Git 提交。

## 回滚到旧站

1. 打开 **Actions → Deploy blog → Run workflow**。
2. 分支保持 **astro-source**，version 选择 **legacy**，运行。
3. 工作流会上传 `hexo-live-before-astro` 中冻结的静态旧站，无需重装 Hexo 或 Node 16。检查部署成功后访问首页和旧文章地址。

恢复新站时按相同步骤将 version 选为 **astro**。回滚后推送 `astro-source` 会再次发布新站，因此临时保留旧站期间请勿向该分支推送。

旧站备份分支保持不动；迁移前仓库历史仍保存在 Git 中。另有本机全量备份与历史 bundle，位于 `../blog-backups/20261105-185137/`，该目录不属于部署产物。

## 目录

- `site/src/content/blog/`：文章与元数据
- `site/src/pages/`：页面和静态 JSON / RSS 端点
- `site/src/layouts/`、`site/src/components/`：布局和复用组件
- `site/src/styles/global.css`：全站样式
- `site/public/images/`：旧站头像与图标
- `site/scripts/`：迁移回归检查与旧站基准数据
- `.github/workflows/deploy.yml`：发布与回滚

部署只上传 `site/dist/`，不会上传源码、node_modules、备份或本机配置。

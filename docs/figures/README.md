# 图表与示意图

集中保存设计文档和演示文档使用的流程图、界面示意图、数据/测试统计图表等源文件或导出图片。文件名应能反映内容和用途，并在对应文档中注明来源及制作人。

## 现有图表

| 文件 | 内容 | 制作人 | 关联任务 |
| --- | --- | --- | --- |
| `ui-interaction.md` | 界面草图配套的交互说明与人工验收步骤 | ljj | P02 |
| `ui-wireframe-main.svg` | 主窗口线框：日历区、列表区、按钮区、状态栏 | ljj | P02 |
| `ui-wireframe-form.svg` | 新增 / 修改共用表单线框与字段级提示 | ljj | P02 |
| `ui-wireframe-dialogs.svg` | 删除确认、错误提示、空状态三个对话框 | ljj | P02 |
| `ui-delete-flow-unselected.svg` | 「未选中 → 点击删除」状态变化 | ljj | P02 |
| `ui-delete-flow-confirm-cancel.svg` | 「选中 → 确认 → 取消」分支 | ljj | P02 |
| `ui-state-transitions.svg` | 界面四主状态与错误提示的转换总图 | ljj | P02 |

界面部分的阅读顺序：先看 `ui-interaction.md` 第 3 节总体布局，再对照 `ui-wireframe-main.svg`；删除的两条路径看两张 `ui-delete-flow-*.svg`；整体状态关系看 `ui-state-transitions.svg`。

后续存储设计图（xhy）、架构与契约图（zch）按同样的命名前缀追加到本目录，并在上表补注。

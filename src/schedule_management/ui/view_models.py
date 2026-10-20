"""界面层使用的纯数据视图模型。

这里只定义「界面要展示什么」和「界面要提交什么」的形状，不含 Qt 类型、
不含业务规则、不做任何校验。放在单独模块的目的：让 controller 与窗口之间的
数据形状可以脱离 Qt 被直接构造和断言。

三个类型都不是领域对象：它们只是穿越界面边界的信封。
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal

FormMode = Literal["create", "edit"]


@dataclass(frozen=True)
class ScheduleRow:
    """列表里的一行：**展示文本**与**稳定标识**必须同时存在。

    `schedule_id` 与三个展示字段刻意放在一起：界面显示的是格式化后的文本，
    但后续所有操作（修改、删除、查看）都只能拿 id 去调服务。标题可以重复，
    行号会随排序变化，用它们反查记录是本项目明确禁止的做法
    （见 `docs/figures/ui-interaction.md` 第 3 节）。

    `all_day` 是展示文本之外的**语义标记**：全天日程的 `time_text` 是“全天”，
    这句话只能给人看，回填表单时必须还原成空时间，否则保存时会被服务层
    当成非法时间解析。它放在最后并带默认值，既有的四参数构造仍然可用。

    `date` 是搜索与“未来 7 天”列表带来的新需求：搜索结果跨多个日期，
    行如果只带格式化文本，修改时就没有可靠日期可回填。字段放在末尾且
    默认为 `None`，当天列表的旧构造方式保持可用；`None` 表示“日期由
    当前筛选条件隐含”，界面显示为破折号。
    """

    schedule_id: str
    time_text: str
    title_text: str
    notes_text: str
    all_day: bool = False
    date: dt.date | None = None


@dataclass(frozen=True)
class ScheduleDraft:
    """表单提交上来的一份原始输入。

    四个字段一律是**用户原样输入的字符串**，尤其是 `date_text` 与 `time_text`：
    界面不做日期时间解析，也不先把它们转成 `date` / `time`。
    理由见 `ui-interaction.md` 5.1 节——宽容解析是后端职责（zch 在 PR #5
    审查中的意见），界面一旦先拦一道，就等于把"合不合法"的判定权收回前端。
    """

    title: str
    date_text: str
    time_text: str
    notes: str


@dataclass(frozen=True)
class FormRequest:
    """打开表单时交给界面的上下文。

    新增与修改共用同一个表单窗口，差别只有窗口标题和是否预填，因此这里把
    「怎么开」也建模成数据：`mode` 决定后台调用哪个用例，`initial` 为空即空白表单。

    失败重试时复用同一个数据对象：只要替换 `initial` 为用户上一次的草稿，
    就能保证"写入失败保留已填内容"（`ui-interaction.md` 5.2 节）。
    """

    mode: FormMode
    heading: str
    initial: ScheduleDraft | None = None

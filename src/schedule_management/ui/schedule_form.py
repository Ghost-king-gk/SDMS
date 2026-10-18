"""新增 / 修改共用的表单（第 4 节表单态）。

**一个窗口两种用途**：差别只在标题和是否预填，代码复制两遍是让两个入口的
行为悄悄漂移的最快办法。

本模块最重要的纪律是：**不校验任何字段**。用户写什么就交什么——
日期 `2026/10/15`、甚至 `明天` 都要原样送到后端去（5.1 节，zch 在 PR #5 的
意见）。这里既没有红框，也没有"格式不正确"，连长度都不限制。

表单也没有"保存失败后留在原地"的逻辑：失败时 controller 会拿着用户上一次的
草稿**再开一次**表单（`controller._run_form`），所以这里只需要做一件事——
把上一次的 `initial` 原样填回去。
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .date_picker import pick_date
from .view_models import FormRequest, ScheduleDraft

_FIELD_LABELS = ("标题", "日期", "时间", "备注")


class ScheduleForm(QDialog):
    """四个字段的表单。确定返回一份原始草稿，取消返回 None。"""

    def __init__(self, request: FormRequest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(request.heading)
        self.setMinimumWidth(360)

        self._title = QLineEdit(self)
        self._date = QLineEdit(self)
        self._time = QLineEdit(self)
        self._notes = QTextEdit(self)

        self._title.setPlaceholderText("必填")
        self._date.setPlaceholderText("YYYY-MM-DD，也可以写 2026/10/15")
        self._time.setPlaceholderText("HH:MM")
        self._notes.setPlaceholderText("选填")

        self._pick_button = QPushButton("选择", self)
        date_row = QHBoxLayout()
        date_row.addWidget(self._date, 1)
        date_row.addWidget(self._pick_button)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")

        form = QVBoxLayout(self)
        form.addWidget(QLabel(_FIELD_LABELS[0], self))
        form.addWidget(self._title)
        form.addWidget(QLabel(_FIELD_LABELS[1], self))
        form.addLayout(date_row)
        form.addWidget(QLabel(_FIELD_LABELS[2], self))
        form.addWidget(self._time)
        form.addWidget(QLabel(_FIELD_LABELS[3], self))
        form.addWidget(self._notes)
        form.addWidget(self._buttons)

        self._pick_button.clicked.connect(self._open_date_picker)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        initial = request.initial
        if initial is not None:
            self._fill(initial)

    # ------------------------------------------------------------------ 对外

    def draft(self) -> ScheduleDraft:
        """用户当前输入的**原始文本**：不解析、不去空白、不补格式。"""
        return ScheduleDraft(
            title=self._title.text(),
            date_text=self._date.text(),
            time_text=self._time.text(),
            notes=self._notes.toPlainText(),
        )

    # ------------------------------------------------------------------ 内部

    def _fill(self, draft: ScheduleDraft) -> None:
        self._title.setText(draft.title)
        self._date.setText(draft.date_text)
        self._time.setText(draft.time_text)
        self._notes.setPlainText(draft.notes)

    def _open_date_picker(self) -> None:
        """用户取消时什么都不做——输入框里原有的文本必须保持原样。"""
        chosen = pick_date(initial=self._current_day_if_any(), parent=self)
        if chosen is None:
            return
        self._date.setText(chosen.isoformat())

    def _current_day_if_any(self) -> dt.date | None:
        """浮层打开时尽量落在已有文本所指的那天；读不出来就从今天开始。"""
        try:
            return dt.date.fromisoformat(self._date.text().strip())
        except ValueError:
            return None


def open_schedule_form(request: FormRequest, parent: QWidget | None = None) -> ScheduleDraft | None:
    """打开表单；保存返回草稿，取消或关闭返回 None。

    把"可能是 None"这个判断收在这里，`MainViewPort` 的实现就只需一行。
    """
    form = ScheduleForm(request, parent)
    if form.exec() != QDialog.DialogCode.Accepted:
        return None
    return form.draft()


__all__ = ["ScheduleForm", "open_schedule_form"]

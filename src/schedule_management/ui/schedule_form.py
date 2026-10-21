"""新增 / 修改共用的表单（第 4 节表单态）。

**一个窗口两种用途**：差别只在标题和是否预填，代码复制两遍是让两个入口的
行为悄悄漂移的最快办法。

本模块最重要的纪律是：**不校验任何字段**。用户写什么就交什么——
日期 `2026/10/15`、甚至 `明天` 都要原样送到后端去（5.1 节，zch 在 PR #5 的
意见）。这里既没有红框拦提交，也没有"格式不正确"，连长度都不限制。

唯一的例外是**提示、不是拦截**：标题为空时输入框边框变红（后端必定拒绝，
提前说一句比等一次往返好），标题超过 80 字时下面给一行"列表里会截断"的
说明——但两者都照旧允许保存，判定权仍在后端。

保存失败不再"关掉表单再开一次"：控制器带着原草稿和错误文案重新请求，
窗口复用同一个对话框实例，把结论显示在表单顶部的错误条里（5.2 节）。
"""

from __future__ import annotations

import datetime as dt

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QCompleter,
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

#: 标题的软上限：超过只提示"列表里会截断"，不禁止保存。
#: 硬限（`setMaxLength`）会把已经想好的标题生生截掉，比截断显示更糟。
_TITLE_SOFT_LIMIT = 80

#: 时间框的候选：整点为主，补几个常见的半点。只做**建议**，不做约束——
#: 用户可以继续手打 `9:5` 这种写法，交给后端宽容解析。
_TIME_SUGGESTIONS = (
    *(f"{hour:02d}:00" for hour in range(7, 24)),
    "07:30",
    "08:30",
    "09:30",
    "12:30",
    "13:30",
    "14:30",
    "18:30",
    "19:30",
    "20:30",
)


class ScheduleForm(QDialog):
    """四个字段的表单。确定返回一份原始草稿，取消返回 None。"""

    def __init__(self, request: FormRequest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(request.heading)
        self.setMinimumWidth(360)
        self._request_mode = request.mode

        self._title = QLineEdit(self)
        self._date = QLineEdit(self)
        self._time = QLineEdit(self)
        self._notes = QTextEdit(self)

        self._title.setPlaceholderText("例如：周报提交")
        self._date.setPlaceholderText("YYYY-MM-DD，也可以写 2026/10/15")
        self._time.setPlaceholderText("HH:MM（输入或展开时有常用时间）")
        # 用 QLineEdit + QCompleter 而不是 QComboBox：下拉只是"省得手打"，
        # 输入框仍然是自由文本，`9:5`、`9点30` 这类写法照样能交上去。
        time_completer = QCompleter(sorted(set(_TIME_SUGGESTIONS)), self)
        time_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        time_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        time_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._time.setCompleter(time_completer)
        self._notes.setPlaceholderText("选填")

        # 「全天」是个勾选框而不是"时间留空就行"：空着的输入框看不出这是
        # 一种正常状态，placeholder 一打字就消失，用户只能猜。勾上就禁用时间框，
        # 提交时仍然交原始字符串（空串），判定全天的权力还是在后端。
        self._all_day = QCheckBox("全天（不指定具体时刻）", self)
        self._all_day.setObjectName("AllDay")

        self._pick_button = QPushButton("选择", self)
        self._pick_button.setObjectName("PickButton")
        date_row = QHBoxLayout()
        date_row.addWidget(self._date, 1)
        date_row.addWidget(self._pick_button)

        time_row = QHBoxLayout()
        time_row.addWidget(self._time, 1)
        time_row.addWidget(self._all_day)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("保存")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")

        # 错误条常驻在顶部但默认隐藏：保存失败时就地显示，表单不再关掉重开。
        # 放在字段上方而不是用 QMessageBox，是因为用户需要一边看结论一边改。
        self._error_label = QLabel("", self)
        self._error_label.setObjectName("FormError")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)

        # 标题后面挂一颗红点表示必填：placeholder 里的"必填"一打字就没了，
        # 看不出哪个字段是硬性的。
        title_label = QLabel(_FIELD_LABELS[0], self)
        required_mark = QLabel("*", self)
        required_mark.setObjectName("RequiredMark")
        title_row = QHBoxLayout()
        title_row.setSpacing(2)
        title_row.addWidget(title_label)
        title_row.addWidget(required_mark)
        title_row.addStretch(1)

        # 超长提示：只是说明"列表里会截断"，不拦保存——判定权仍在后端。
        self._title_hint = QLabel("", self)
        self._title_hint.setObjectName("FieldHint")
        self._title_hint.setWordWrap(True)
        self._title_hint.setVisible(False)

        form = QVBoxLayout(self)
        form.addWidget(self._error_label)
        form.addLayout(title_row)
        form.addWidget(self._title)
        form.addWidget(self._title_hint)
        form.addWidget(QLabel(_FIELD_LABELS[1], self))
        form.addLayout(date_row)
        form.addWidget(QLabel(_FIELD_LABELS[2], self))
        form.addLayout(time_row)
        form.addWidget(QLabel(_FIELD_LABELS[3], self))
        form.addWidget(self._notes)
        form.addWidget(self._buttons)

        self._pick_button.clicked.connect(self._open_date_picker)
        self._all_day.toggled.connect(self._on_all_day_toggled)
        self._title.textChanged.connect(self._sync_title_state)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        self.apply(request)

    # ------------------------------------------------------------------ 对外

    def apply(self, request: FormRequest) -> None:
        """按新的请求刷新同一个对话框：标题、模式、预填内容、错误条。

        保存失败后 controller 会带着原草稿和错误结论再来一次。复用同一个实例
        而不是新建一个，用户看到的是**自己刚才填的那份东西 + 顶部多了一句原因**，
        而不是一个框闪一下、位置还跳到屏幕中间。
        """
        self._request_mode = request.mode
        self.setWindowTitle(request.heading)
        if request.initial is not None:
            self._fill(request.initial)
        else:
            self._clear_fields()
        self.show_inline_error(request.error)
        self._sync_title_state()

    def show_inline_error(self, message: str) -> None:
        """在表单顶部显示后端结论；空串即收起。"""
        self._error_label.setText(message)
        self._error_label.setVisible(bool(message.strip()))

    def draft(self) -> ScheduleDraft:
        """用户当前输入的**原始文本**：不解析、不去空白、不补格式。

        勾了「全天」时间一律交空串——空串在后端就是"没有具体时刻"，
        这里不再自创第三种写法。
        """
        return ScheduleDraft(
            title=self._title.text(),
            date_text=self._date.text(),
            time_text="" if self._all_day.isChecked() else self._time.text(),
            notes=self._notes.toPlainText(),
        )

    # ------------------------------------------------------------------ 内部

    def _clear_fields(self) -> None:
        """空白表单：四个框清空，全天勾选回到未勾（新建时不该默认禁用时间框）。"""
        self._title.clear()
        self._date.clear()
        self._time.clear()
        self._notes.clear()
        self._all_day.setChecked(False)

    def _sync_title_state(self) -> None:
        """标题的两种提示：为空时边框变红，过长时说明会截断。

        两者都不拦保存——后端才是判定方，这里只是把"一定会被拒"和"会被折叠"
        提前说出来，省用户一次往返。
        """
        text = self._title.text()
        missing = not text.strip()
        if self._title.property("requiredMissing") != missing:
            self._title.setProperty("requiredMissing", missing)
            # QSS 的属性选择器只在重新 polish 之后才生效。
            style = self._title.style()
            style.unpolish(self._title)
            style.polish(self._title)
        too_long = len(text.strip()) > _TITLE_SOFT_LIMIT
        self._title_hint.setVisible(too_long)
        if too_long:
            length = len(text.strip())
            self._title_hint.setText(
                f"标题 {length} 字，超过 {_TITLE_SOFT_LIMIT} 字在列表里会被截断显示（仍可保存）。"
            )

    def _fill(self, draft: ScheduleDraft) -> None:
        self._title.setText(draft.title)
        self._date.setText(draft.date_text)
        self._time.setText(draft.time_text)
        self._notes.setPlainText(draft.notes)
        # 只有修改一条**已经**是全天的日程时才预勾：新建时若默认勾上，
        # 时间框会被禁用，用户反而看不到最主要的输入位置。
        # 复用的对话框必须先复位一次，否则上一条的"全天"会带到下一条上。
        if self._request_mode == "edit" and not draft.time_text.strip():
            self._all_day.setChecked(True)
        else:
            self._all_day.setChecked(False)

    def _on_all_day_toggled(self, checked: bool) -> None:
        """勾上就清空并禁用时间框；取消勾选把焦点交回时间框。"""
        self._time.setEnabled(not checked)
        if checked:
            self._time.clear()
        else:
            self._time.setFocus()

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

"""排水设施业务规则：台账、疏通登记、复核三段数据分开存放，进度统一从登记/复核记录派生。

数据分三张表（均为只追加，登记与复核永不互相覆盖）：
- drain          设施台账：设施编号、管径规格、淤积深度等静态信息；
- drain.records  疏通登记：疏通队伍登记一次就追加一条，携带设施编号与登记时的台账快照；
- drain.reviews  复核记录：复核一次追加一条，按 record_id 挂在对应登记上。

进度口径（列表页、详情页、复核弹窗共用本文件的 progress/serialize，保证三处一致）：
- 设施没有任何疏通登记            -> 待疏通
- 最新一条疏通登记还没有复核记录  -> 疏通中
- 最新一条疏通登记已有复核记录    -> 已复核
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "drain"
RECORDS_MODULE = "drain.records"
REVIEWS_MODULE = "drain.reviews"

REQUIRED_FIELDS = ["设施编号", "设施类型", "所在路段", "管径规格"]
MASTER_FIELDS = ["设施编号", "设施类型", "所在路段", "管径规格", "淤积深度"]

PROGRESS_PENDING = "待疏通"
PROGRESS_DOING = "疏通中"
PROGRESS_REVIEWED = "已复核"
PROGRESS_ORDER = [PROGRESS_PENDING, PROGRESS_DOING, PROGRESS_REVIEWED]

REVIEW_RESULTS = ["合格", "不合格"]


def _today() -> str:
    return date.today().isoformat()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


INVALID_DATE = object()


def _parse_day(value: Any) -> str | None | object:
    """疏通/复核日期只接受 YYYY-MM-DD；空串返回 None，非法格式返回 INVALID_DATE 哨兵。"""
    text = _clean(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return INVALID_DATE


class DrainService:
    # ---- 基础读取 ----------------------------------------------------------

    def _facilities(self) -> list[dict[str, Any]]:
        return store.rows(MODULE)

    def _records(self) -> list[dict[str, Any]]:
        return store.rows(RECORDS_MODULE)

    def _reviews(self) -> list[dict[str, Any]]:
        return store.rows(REVIEWS_MODULE)

    def _find_facility(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def _find_facility_by_code(self, code: str) -> dict[str, Any] | None:
        for row in self._facilities():
            if _clean(row.get("设施编号")) == code:
                return row
        return None

    def _find_record(self, record_id: int) -> dict[str, Any] | None:
        for row in self._records():
            if int(row.get("id", 0)) == record_id:
                return row
        return None

    def _find_review(self, record_id: int) -> dict[str, Any] | None:
        for row in self._reviews():
            if int(row.get("record_id", 0)) == record_id:
                return row
        return None

    def _facility_records(self, code: str) -> list[dict[str, Any]]:
        return [row for row in self._records() if _clean(row.get("设施编号")) == code]

    def _active_record(self, code: str) -> dict[str, Any] | None:
        """当前在办的疏通登记：正常登记优先于历史补录；同类型按登记先后取最新一条。

        补录的历史记录不允许顶掉当前在办周期，所以用 历史补录 标记隔开两段数据。
        """
        normal = [r for r in self._facility_records(code) if not r.get("历史补录")]
        candidates = normal or self._facility_records(code)
        if not candidates:
            return None
        return max(candidates, key=lambda r: int(r.get("id", 0)))

    def progress_of(self, facility: dict[str, Any]) -> str:
        record = self._active_record(_clean(facility.get("设施编号")))
        if record is None:
            return PROGRESS_PENDING
        return PROGRESS_REVIEWED if self._find_review(int(record["id"])) else PROGRESS_DOING

    def _serialize(self, facility: dict[str, Any]) -> dict[str, Any]:
        """台账 + 当前在办登记 + 其复核 拼成同一份视图，列表/详情/弹窗都用它。"""
        code = _clean(facility.get("设施编号"))
        progress = self.progress_of(facility)
        view = {
            "id": facility.get("id"),
            "设施编号": code,
            "设施类型": facility.get("设施类型", ""),
            "所在路段": facility.get("所在路段", ""),
            "管径规格": facility.get("管径规格", ""),
            "淤积深度": facility.get("淤积深度", ""),
            "疏通日期": "",
            "养护人员": "",
            "疏通队伍": "",
            "复核日期": "",
            "复核人": "",
            "复核结果": "",
            "进度": progress,
            "status": progress,
            "active_record_id": None,
            "历史条数": len(self._facility_records(code)),
            "pending": progress != PROGRESS_REVIEWED,
            "abnormal": False,
        }
        record = self._active_record(code)
        if record is not None:
            view["active_record_id"] = record["id"]
            view["疏通日期"] = record.get("疏通日期", "")
            view["养护人员"] = record.get("养护人员", "")
            view["疏通队伍"] = record.get("疏通队伍", "")
            review = self._find_review(int(record["id"]))
            if review is not None:
                view["复核日期"] = review.get("复核日期", "")
                view["复核人"] = review.get("复核人", "")
                view["复核结果"] = review.get("复核结果", "")
        return view

    # ---- 列表 / 详情 / 统计 -------------------------------------------------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        progress: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._serialize(row) for row in self._facilities()]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设施编号", ""))]
        if progress:
            rows = [row for row in rows if row["进度"] == progress]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def progress_stats(self) -> dict[str, int]:
        stats = {name: 0 for name in PROGRESS_ORDER}
        for row in self._facilities():
            stats[self.progress_of(row)] += 1
        return stats

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        facility = self._find_facility(entry_id)
        if facility is None:
            return None
        view = self._serialize(facility)
        code = view["设施编号"]
        history: list[dict[str, Any]] = []
        for record in sorted(
            self._facility_records(code),
            key=lambda r: (str(r.get("疏通日期", "")), int(r.get("id", 0))),
            reverse=True,
        ):
            review = self._find_review(int(record["id"]))
            history.append({
                "record_id": record["id"],
                "疏通日期": record.get("疏通日期", ""),
                "养护人员": record.get("养护人员", ""),
                "疏通队伍": record.get("疏通队伍", ""),
                "登记时淤积深度": record.get("登记时淤积深度", ""),
                "登记时间": record.get("登记时间", ""),
                "历史补录": bool(record.get("历史补录")),
                "复核日期": review.get("复核日期", "") if review else "",
                "复核人": review.get("复核人", "") if review else "",
                "复核结果": review.get("复核结果", "") if review else "",
            })
        view["疏通记录"] = history
        return view

    # ---- 台账登记 -----------------------------------------------------------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not _clean(values.get(field))]
        if missing:
            return None, missing
        code = _clean(values["设施编号"])
        if self._find_facility_by_code(code):
            return None, ["设施编号重复"]
        rows = self._facilities()
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in MASTER_FIELDS:
            entry[field] = _clean(values.get(field))
        rows.append(entry)
        return self._serialize(entry), []

    # ---- 疏通登记（批量，整批预检，一个不通过整批不落库） ----------------------

    def _check_dredge_item(self, item: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """校验单条疏通登记，返回 (设施台账, 阻断原因)，阻断原因里带上设施编号。"""
        code = _clean(item.get("设施编号"))
        if not code:
            return None, "设施编号为空"
        day = _parse_day(item.get("疏通日期"))
        if day is INVALID_DATE:
            return None, f"{code}：疏通日期格式应为 YYYY-MM-DD"
        if not day:
            return None, f"{code}：疏通日期为空"
        facility = self._find_facility_by_code(code)
        if facility is None:
            return None, f"{code}：设施编号不存在"
        if not _clean(facility.get("管径规格")):
            return None, f"{code}：管径规格为空，不允许提交疏通登记"
        active = self._active_record(code)
        if active is not None and self._find_review(int(active["id"])) is None:
            return None, (
                f"{code}：存在未复核的疏通登记（疏通日期 {active.get('疏通日期', '—')}），"
                "请先复核后再登记新一轮疏通"
            )
        return facility, ""

    def _append_record(self, facility: dict[str, Any], item: dict[str, Any], *, backfill: bool) -> dict[str, Any]:
        code = _clean(facility["设施编号"])
        rows = self._records()
        parsed = _parse_day(item.get("疏通日期"))
        record = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "设施编号": code,
            "疏通日期": parsed if isinstance(parsed, str) else "",
            "养护人员": _clean(item.get("养护人员")),
            "疏通队伍": _clean(item.get("疏通队伍")),
            # 台账快照：疏通日期永远跟着当时的设施编号与淤积深度走，重开详情不会串号
            "登记时淤积深度": _clean(facility.get("淤积深度")),
            "登记时间": _now(),
            "历史补录": backfill,
        }
        if _clean(item.get("client_key")):
            record["client_key"] = _clean(item.get("client_key"))
        rows.append(record)
        return record

    def register_dredge_batch(
        self, items: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """整批预检：任何一条被阻断，整批都不写库，并列出全部被阻断的设施编号与原因。"""
        if not items:
            return [], ["提交内容为空，没有可登记的疏通记录"]
        checked: list[tuple[dict[str, Any], dict[str, Any]]] = []
        blocked: list[str] = []
        seen: set[str] = set()
        for item in items:
            code = _clean(item.get("设施编号"))
            if code in seen:
                blocked.append(f"{code or '（空）'}：同一批次里重复提交")
                continue
            seen.add(code)
            facility, reason = self._check_dredge_item(item)
            if facility is None:
                blocked.append(reason)
            else:
                checked.append((facility, item))
        if blocked:
            return [], blocked
        appended: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for facility, item in checked:
            appended.append((facility, self._append_record(facility, item, backfill=False)))
        # 登记落库后再序列化，保证返回视图带最新进度与疏通日期
        return [self._serialize(facility) for facility, _ in appended], []

    # ---- 修改疏通日期（仅未复核记录） ----------------------------------------

    def update_dredge(
        self, record_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        record = self._find_record(record_id)
        if record is None:
            return None, f"疏通登记 {record_id} 不存在"
        if self._find_review(record_id) is not None:
            return None, "该疏通记录已复核，不允许再修改疏通日期"
        day = _parse_day(values.get("疏通日期"))
        if day is INVALID_DATE:
            return None, "疏通日期格式应为 YYYY-MM-DD"
        if not day:
            return None, "疏通日期为空，未做修改"
        record["疏通日期"] = day
        if "养护人员" in values:
            record["养护人员"] = _clean(values.get("养护人员"))
        if "疏通队伍" in values:
            record["疏通队伍"] = _clean(values.get("疏通队伍"))
        facility = self._find_facility_by_code(_clean(record.get("设施编号")))
        return self._serialize(facility), "" if facility else "对应设施台账缺失"

    # ---- 复核（追加写，不动疏通登记） ----------------------------------------

    def review_record(
        self, record_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        record = self._find_record(record_id)
        if record is None:
            return None, f"疏通登记 {record_id} 不存在"
        if self._find_review(record_id) is not None:
            return None, "该疏通记录已复核，不能重复复核，也不能再改疏通日期"
        day = _parse_day(values.get("复核日期"))
        if day is INVALID_DATE:
            return None, "复核日期格式应为 YYYY-MM-DD"
        if not day:
            day = _today()
        reviewer = _clean(values.get("复核人"))
        if not reviewer:
            return None, "复核人为空，不允许通过复核"
        result = _clean(values.get("复核结果")) or REVIEW_RESULTS[0]
        if result not in REVIEW_RESULTS:
            return None, f"复核结果只能是 {'、'.join(REVIEW_RESULTS)}"
        rows = self._reviews()
        rows.append({
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
            "record_id": record_id,
            "设施编号": record.get("设施编号", ""),
            "复核日期": day,
            "复核人": reviewer,
            "复核结果": result,
            "复核时间": _now(),
        })
        facility = self._find_facility_by_code(_clean(record.get("设施编号")))
        return self._serialize(facility), ""

    # ---- 补录（逐条独立，失败不影响其他条；client_key 防重试重复落库） ----------

    def backfill(
        self, items: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """返回 (成功条目, 失败条目)；失败条目原样带回 payload，前端可只重试这一条。"""
        succeeded: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for raw in items:
            item = dict(raw)
            code = _clean(item.get("设施编号"))
            client_key = _clean(item.get("client_key"))
            if client_key:
                dup = next(
                    (r for r in self._records() if r.get("client_key") == client_key),
                    None,
                )
                if dup is not None:
                    facility = self._find_facility_by_code(code)
                    succeeded.append({
                        "client_key": client_key,
                        "设施编号": code,
                        "疏通日期": dup.get("疏通日期", ""),
                        "record_id": dup.get("id"),
                        "dedup": True,
                        "view": self._serialize(facility) if facility else None,
                    })
                    continue
            facility, reason = self._check_backfill_item(item)
            if facility is None:
                failed.append({"client_key": client_key, "设施编号": code or "（空）", "reason": reason, "payload": item})
                continue
            record = self._append_record(facility, item, backfill=True)
            review_info = ""
            if _clean(item.get("复核日期")) or _clean(item.get("复核人")):
                review, review_reason = self._validate_embedded_review(item)
                if review is None:
                    failed.append({"client_key": client_key, "设施编号": code, "reason": review_reason, "payload": item})
                    self._records().remove(record)
                    continue
                rows = self._reviews()
                rows.append({
                    "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
                    "record_id": record["id"],
                    "设施编号": code,
                    "复核日期": review[0],
                    "复核人": review[1],
                    "复核结果": review[2],
                    "复核时间": _now(),
                })
                review_info = review[0]
            succeeded.append({
                "client_key": client_key,
                "设施编号": code,
                "疏通日期": record["疏通日期"],
                "record_id": record["id"],
                "dedup": False,
                "复核日期": review_info,
                "view": self._serialize(facility),
            })
        return succeeded, failed

    def _check_backfill_item(
        self, item: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        # 补录是逐条独立成败：同一在办周期里也允许追加更早的历史（标记历史补录，不顶当前周期）
        code = _clean(item.get("设施编号"))
        if not code:
            return None, "设施编号为空"
        day = _parse_day(item.get("疏通日期"))
        if day is INVALID_DATE:
            return None, f"{code}：疏通日期格式应为 YYYY-MM-DD"
        if not day:
            return None, f"{code}：疏通日期为空"
        if not _clean(item.get("养护人员")):
            return None, f"{code}：养护人员为空"
        facility = self._find_facility_by_code(code)
        if facility is None:
            return None, f"{code}：设施编号不存在"
        if not _clean(facility.get("管径规格")):
            return None, f"{code}：管径规格为空，不允许补录疏通记录"
        return facility, ""

    def _validate_embedded_review(
        self, item: dict[str, Any]
    ) -> tuple[tuple[str, str, str] | None, str]:
        day = _parse_day(item.get("复核日期"))
        if day is INVALID_DATE:
            return None, "复核日期格式应为 YYYY-MM-DD"
        if not day:
            return None, "复核日期为空"
        reviewer = _clean(item.get("复核人"))
        if not reviewer:
            return None, "复核人为空"
        result = _clean(item.get("复核结果")) or REVIEW_RESULTS[0]
        if result not in REVIEW_RESULTS:
            return None, f"复核结果只能是 {'、'.join(REVIEW_RESULTS)}"
        return (day, reviewer, result), ""

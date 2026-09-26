"""排水设施业务规则：疏通登记按 待疏通 / 疏通中 / 已复核 三段分桶存放。

设计要点：
- 每条疏通记录只生活在一个阶段的桶里，流转时整条记录搬运，疏通日期等字段不丢；
- 疏通日期只按记录 id 写入，记录自身携带设施编号，不会串到别的设施上；
- 已复核的记录不允许再改疏通日期；新增记录只追加，历史疏通记录不被覆盖；
- 管径规格为空、设施编号不存在都会被阻断，并说明原因、列出被阻断的设施编号。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "drain"
REQUIRED_FIELDS = ["设施编号", "设施类型", "所在路段"]
STAGES = ["待疏通", "疏通中", "已复核"]
FLOW_BUCKETS = {stage: f"drain_flow:{stage}" for stage in STAGES}
FLOW_FIELDS = ["设施编号", "管径规格", "淤积深度", "养护人员", "疏通日期", "备注"]


class DrainService:
    # ---------- 设施台账 ----------
    def list_facilities(
        self,
        *,
        keyword: str | None = None,
        stage: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._enrich_facility(row) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设施编号", ""))]
        if stage:
            rows = [row for row in rows if row.get("疏通进度") == stage]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_facility(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        detail = self._enrich_facility(row)
        detail["疏通记录"] = self._records_of(str(row.get("设施编号", "")))
        return detail

    def create_facility(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["管径规格"] = values.get("管径规格")
        entry["淤积深度"] = values.get("淤积深度")
        entry["排水状态"] = values.get("排水状态") or "畅通"
        entry["status"] = entry["排水状态"]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    # ---------- 三段分桶：统计与查询 ----------
    def summary(self) -> dict[str, int]:
        """三段各自的记录数；列表页、详情页、复核弹窗共用这一份口径。"""
        return {stage: len(store.rows(bucket)) for stage, bucket in FLOW_BUCKETS.items()}

    def list_flow(self, *, stage: str | None = None, keyword: str | None = None) -> list[dict[str, Any]]:
        stages = [stage] if stage in FLOW_BUCKETS else STAGES
        records: list[dict[str, Any]] = []
        for name in stages:
            records.extend(dict(row) for row in store.rows(FLOW_BUCKETS[name]))
        if keyword:
            records = [row for row in records if keyword in str(row.get("设施编号", ""))]
        records.sort(key=lambda row: int(row.get("id", 0)))
        return records

    # ---------- 疏通登记 ----------
    def create_flow(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """补录一条疏通记录；已带疏通日期的直接进疏通中，否则进待疏通。"""
        errors = self._validate_flow(values)
        if errors:
            return None, errors
        dredge_date = str(values.get("疏通日期") or "").strip() or None
        record: dict[str, Any] = {
            "id": self._next_flow_id(),
            "stage": "疏通中" if dredge_date else "待疏通",
            "登记时间": date.today().isoformat(),
            "复核人": None,
            "复核时间": None,
        }
        record.update({field: values.get(field) for field in FLOW_FIELDS})
        record["设施编号"] = str(record["设施编号"]).strip()
        record["管径规格"] = str(record["管径规格"]).strip()
        record["疏通日期"] = dredge_date
        store.rows(FLOW_BUCKETS[record["stage"]]).append(record)
        return dict(record), []

    def import_flow(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """批量补录：每条独立校验、独立落库；被阻断的设施编号一并列出。"""
        results: list[dict[str, Any]] = []
        blocked: list[str] = []
        for index, item in enumerate(items):
            code = str(item.get("设施编号") or "").strip() or f"第{index + 1}条"
            record, errors = self.create_flow(item)
            if errors:
                blocked.append(code)
                results.append({"index": index, "设施编号": code, "ok": False, "message": "；".join(errors)})
            else:
                results.append({"index": index, "设施编号": code, "ok": True, "message": "已登记", "record": record})
        message = f"共 {len(items)} 条，成功 {len(items) - len(blocked)} 条，阻断 {len(blocked)} 条"
        if blocked:
            message += f"；被阻断的设施编号：{'、'.join(blocked)}"
        return {"ok": not blocked, "message": message, "results": results, "blocked": blocked}

    def register_date(
        self,
        record_id: int,
        *,
        dredge_date: str,
        operator: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """登记疏通日期：只落在记录自身的设施编号上；已复核的拒绝修改。"""
        found = self._find_flow(record_id)
        if found is None:
            return None, f"疏通记录 {record_id} 不存在或已归档"
        record = found
        if record["stage"] == "已复核":
            return None, f"疏通记录 {record_id} 已复核，不允许再改疏通日期"
        errors = self._validate_date(dredge_date)
        if errors:
            return None, "；".join(errors)
        record["疏通日期"] = dredge_date
        if operator:
            record["养护人员"] = operator
        if record["stage"] != "疏通中":
            self._move(record, "疏通中")
        return dict(record), f"疏通记录 {record_id} 已登记疏通日期，进度更新为疏通中"

    def review_flow(self, record_id: int, *, reviewer: str | None = None) -> tuple[dict[str, Any] | None, str]:
        """复核：整条记录从疏通中搬到已复核，疏通日期随记录保留并锁定。"""
        record = self._find_flow(record_id)
        if record is None:
            return None, f"疏通记录 {record_id} 不存在或已归档"
        if record["stage"] == "待疏通":
            return None, f"疏通记录 {record_id} 还未登记疏通日期，不能复核"
        if record["stage"] == "已复核":
            return None, f"疏通记录 {record_id} 已复核，请勿重复操作"
        record["复核人"] = reviewer or record.get("复核人") or "值班复核员"
        record["复核时间"] = date.today().isoformat()
        self._move(record, "已复核")
        return dict(record), f"疏通记录 {record_id} 已复核，疏通日期 {record['疏通日期']} 已锁定"

    # ---------- 内部工具 ----------
    def _enrich_facility(self, row: dict[str, Any]) -> dict[str, Any]:
        """列表/详情共用的进度口径：取该设施最新一条疏通记录的阶段。"""
        data = dict(row)
        records = self._records_of(str(row.get("设施编号", "")))
        latest = records[-1] if records else None
        data["疏通进度"] = latest["stage"] if latest else "未登记"
        data["最新疏通日期"] = latest.get("疏通日期") if latest else None
        data["养护人员"] = latest.get("养护人员") if latest else None
        return data

    def _records_of(self, code: str) -> list[dict[str, Any]]:
        records = [
            dict(row)
            for bucket in FLOW_BUCKETS.values()
            for row in store.rows(bucket)
            if str(row.get("设施编号", "")) == code
        ]
        records.sort(key=lambda row: int(row.get("id", 0)))
        return records

    @staticmethod
    def _find_flow(record_id: int) -> dict[str, Any] | None:
        for bucket in FLOW_BUCKETS.values():
            for row in store.rows(bucket):
                if int(row.get("id", 0)) == record_id:
                    return row
        return None

    @staticmethod
    def _move(record: dict[str, Any], target_stage: str) -> None:
        store.rows(FLOW_BUCKETS[record["stage"]]).remove(record)
        record["stage"] = target_stage
        store.rows(FLOW_BUCKETS[target_stage]).append(record)

    @staticmethod
    def _next_flow_id() -> int:
        ids = [
            int(row.get("id", 0))
            for bucket in FLOW_BUCKETS.values()
            for row in store.rows(bucket)
        ]
        return max(ids, default=0) + 1

    def _validate_flow(self, values: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        code = str(values.get("设施编号") or "").strip()
        if not code:
            errors.append("设施编号为空，疏通记录必须挂在对应的设施编号上")
        elif not self._facility_exists(code):
            errors.append(f"设施编号 {code} 不存在，疏通日期只能落在已登记的设施编号上")
        if not str(values.get("管径规格") or "").strip():
            errors.append("管径规格为空，不允许提交，请补充管径规格后重试")
        dredge_date = str(values.get("疏通日期") or "").strip()
        if dredge_date:
            errors.extend(self._validate_date(dredge_date))
        return errors

    @staticmethod
    def _validate_date(value: str) -> list[str]:
        try:
            datetime.strptime(str(value).strip(), "%Y-%m-%d")
        except (TypeError, ValueError):
            return [f"疏通日期「{value}」格式应为 YYYY-MM-DD"]
        return []

    @staticmethod
    def _facility_exists(code: str) -> bool:
        return any(str(row.get("设施编号", "")) == code for row in store.rows(MODULE))

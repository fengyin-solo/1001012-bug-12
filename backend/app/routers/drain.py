"""排水设施接口：台账、疏通登记、复核分三段管理，进度口径与阻断原因都从这里透出。

路由顺序：具体路径（stats/export、dredge/backfill 批量入口）放在 /{entry_id}
通配路由之前，避免具体路径被当成设施 id 解析。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import (
    ActionResult,
    DrainBackfillResult,
    DrainBatchPayload,
    DrainBatchResult,
    EntryPayload,
    PageResult,
)
from app.services.drain import PROGRESS_ORDER, DrainService

router = APIRouter(prefix="/api/drain", tags=["排水设施"])

service = DrainService()

LIST_FIELDS = [
    "设施编号",
    "设施类型",
    "所在路段",
    "管径规格",
    "淤积深度",
    "疏通日期",
    "养护人员",
    "进度",
]
STATUSES = PROGRESS_ORDER


@router.get("/stats", response_model=dict)
def progress_stats() -> dict[str, Any]:
    """三段进度的数量统计，列表页卡片直接用它，避免各页各算一套。"""
    return {"stats": service.progress_stats()}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按设施编号检索"),
    progress: str | None = Query(default=None, description="待疏通、疏通中、已复核"),
    status: str | None = Query(default=None, description="progress 的旧参数名，等价保留"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按设施编号与进度过滤排水设施列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    target = progress or status
    if target and target not in PROGRESS_ORDER:
        raise HTTPException(
            status_code=400,
            detail=f"进度只能是 {'、'.join(PROGRESS_ORDER)}，收到「{target}」",
        )
    items, total = service.list_entries(keyword=keyword, progress=target, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("/dredge", response_model=DrainBatchResult)
def register_dredge(payload: DrainBatchPayload) -> DrainBatchResult:
    """疏通队伍批量登记疏通日期；整批预检，一个不通过整批不落库。"""
    entries, blocked = service.register_dredge_batch(payload.items)
    if blocked:
        return DrainBatchResult(
            ok=False,
            message=f"以下 {len(blocked)} 条设施被阻断，整批未提交：{'；'.join(blocked)}",
            blocked=blocked,
        )
    return DrainBatchResult(
        ok=True,
        message=f"已登记 {len(entries)} 条疏通记录",
        entries=entries,
    )


@router.post("/backfill", response_model=DrainBackfillResult)
def backfill_dredge(payload: DrainBatchPayload) -> DrainBackfillResult:
    """历史疏通记录补录：逐条独立成败，失败条目带回 payload，可只重试这一条。"""
    succeeded, failed = service.backfill(payload.items)
    if not payload.items:
        return DrainBackfillResult(ok=False, message="提交内容为空，没有可补录的记录")
    message = f"补录完成：成功 {len(succeeded)} 条"
    if failed:
        message += f"，失败 {len(failed)} 条，可对失败条目单独重试"
    return DrainBackfillResult(
        ok=not failed,
        message=message,
        succeeded=succeeded,
        failed=failed,
    )


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出排水设施清单：返回全部设施在统一进度口径下的数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "drain", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条排水设施明细（含历史疏通记录）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"排水设施 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条排水设施台账；管径规格等必填项缺失时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="排水设施已登记", entry=entry)


@router.patch("/records/{record_id}", response_model=ActionResult)
def update_dredge(record_id: int, payload: EntryPayload) -> ActionResult:
    """修改疏通日期/养护人员；已复核的记录不允许再改。"""
    entry, message = service.update_dredge(record_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="疏通信息已更新", entry=entry)


@router.post("/records/{record_id}/review", response_model=ActionResult)
def review_record(record_id: int, payload: EntryPayload) -> ActionResult:
    """复核疏通登记：复核数据单独追加存放，不覆盖疏通日期等登记内容。"""
    entry, message = service.review_record(record_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="疏通记录已复核", entry=entry)

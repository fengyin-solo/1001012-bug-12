"""排水设施接口：设施台账 + 疏通登记三段流转（待疏通 / 疏通中 / 已复核）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, FlowImportPayload, FlowImportResult, PageResult
from app.services.drain import STAGES, DrainService

router = APIRouter(prefix="/api/drain", tags=["排水设施"])

service = DrainService()


@router.get("/summary")
def flow_summary() -> dict[str, Any]:
    """三段进度统计：列表页、详情页、复核弹窗共用这一份口径，保证看到的进度一致。"""
    return {"stages": service.summary()}


@router.get("/flow")
def list_flow(
    stage: str | None = Query(default=None, description="待疏通、疏通中、已复核"),
    keyword: str | None = Query(default=None, description="按设施编号检索"),
) -> dict[str, Any]:
    """按阶段查看疏通记录；三段数据分桶存放，互不混排。"""
    if stage is not None and stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"进度「{stage}」不存在，可选：{'、'.join(STAGES)}")
    return {"items": service.list_flow(stage=stage, keyword=keyword)}


@router.post("/flow", response_model=ActionResult)
def create_flow(payload: EntryPayload) -> ActionResult:
    """补录单条疏通记录；校验失败时说明原因并给出被阻断的设施编号，前端可只重试这一条。"""
    record, errors = service.create_flow(payload.values)
    if errors:
        code = str(payload.values.get("设施编号") or "").strip()
        suffix = f"；被阻断的设施编号：{code}" if code else ""
        return ActionResult(ok=False, message=f"{'；'.join(errors)}{suffix}")
    return ActionResult(ok=True, message=f"疏通记录已登记，进度：{record['stage']}", entry=record)


@router.post("/flow/import", response_model=FlowImportResult)
def import_flow(payload: FlowImportPayload) -> FlowImportResult:
    """批量补录：每条独立校验、互不影响；被阻断的设施编号一并列出。"""
    if not payload.items:
        return FlowImportResult(ok=False, message="没有需要补录的疏通记录", results=[], blocked=[])
    return FlowImportResult(**service.import_flow(payload.items))


@router.post("/flow/{record_id}/date", response_model=ActionResult)
def register_date(record_id: int, payload: EntryPayload) -> ActionResult:
    """登记疏通日期：只落在记录自身的设施编号上；已复核的记录拒绝修改。"""
    record, message = service.register_date(
        record_id,
        dredge_date=str(payload.values.get("疏通日期") or "").strip(),
        operator=str(payload.values.get("养护人员") or "").strip() or None,
    )
    if record is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=record)


@router.post("/flow/{record_id}/review", response_model=ActionResult)
def review_flow(record_id: int, payload: EntryPayload) -> ActionResult:
    """复核：整条记录从疏通中搬到已复核，疏通日期随记录保留并锁定。"""
    record, message = service.review_flow(
        record_id,
        reviewer=str(payload.values.get("复核人") or "").strip() or None,
    )
    if record is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=record)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出排水设施清单：返回当前过滤条件下的全量数据（含疏通进度口径）。"""
    items, total = service.list_facilities(page=1, size=10000)
    return {"module": "drain", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按设施编号检索"),
    stage: str | None = Query(default=None, description="按疏通进度过滤：待疏通、疏通中、已复核"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """排水设施列表：疏通进度由服务端按三段分桶统一推导，与详情页、复核弹窗一致。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    if stage is not None and stage not in STAGES:
        raise HTTPException(status_code=400, detail=f"进度「{stage}」不存在，可选：{'、'.join(STAGES)}")
    items, total = service.list_facilities(keyword=keyword, stage=stage, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条排水设施，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_facility(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="排水设施已登记", entry=entry)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """单条排水设施明细：附全部历史疏通记录，新增记录不会覆盖历史。"""
    entry = service.get_facility(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"排水设施 {entry_id} 不存在或已归档")
    return entry

<template>
  <section class="page" data-module="drain">
    <header class="page-head">
      <div>
        <h2>排水设施管理</h2>
        <p class="page-desc">疏通登记按 待疏通 / 疏通中 / 已复核 三段分桶存放，疏通日期只落在对应设施编号的记录上，已复核后锁定。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记排水设施</button>
        <button class="btn primary" type="button" @click="openImport">补录疏通记录</button>
        <button class="btn" type="button" @click="exportRows">导出排水设施清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>设施编号</span>
        <input v-model="filters.keyword" placeholder="按设施编号检索" />
      </label>
      <label class="filter-item">
        <span>疏通进度</span>
        <select v-model="filters.stage">
          <option value="">全部</option>
          <option v-for="stage in stages" :key="stage" :value="stage">{{ stage }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '疏通进度'" class="badge" :class="stageClass(row.疏通进度)">{{ row.疏通进度 }}</span>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无排水设施数据，可先登记排水设施</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条排水设施记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 设施详情：进度与列表页同源，历史疏通记录逐条列出、不被覆盖 -->
    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <h3>排水设施详情 · {{ detail.设施编号 }}</h3>
        <div class="detail-grid">
          <div><span class="detail-label">设施类型</span>{{ detail.设施类型 ?? '—' }}</div>
          <div><span class="detail-label">所在路段</span>{{ detail.所在路段 ?? '—' }}</div>
          <div><span class="detail-label">管径规格</span>{{ detail.管径规格 ?? '—' }}</div>
          <div><span class="detail-label">淤积深度</span>{{ detail.淤积深度 ?? '—' }}</div>
          <div>
            <span class="detail-label">疏通进度</span>
            <span class="badge" :class="stageClass(detail.疏通进度)">{{ detail.疏通进度 }}</span>
          </div>
          <div><span class="detail-label">排水状态</span>{{ detail.排水状态 ?? '—' }}</div>
        </div>

        <h4 class="modal-subtitle">疏通记录（{{ detail.疏通记录?.length ?? 0 }} 条，历史记录只增不改）</h4>
        <table class="data-table">
          <thead>
            <tr>
              <th>记录编号</th>
              <th>管径规格</th>
              <th>淤积深度</th>
              <th>养护人员</th>
              <th>疏通日期</th>
              <th>进度</th>
              <th>复核人</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="record in detail.疏通记录 ?? []" :key="record.id">
              <td>#{{ record.id }}</td>
              <td>{{ record.管径规格 ?? '—' }}</td>
              <td>{{ record.淤积深度 ?? '—' }}</td>
              <td>{{ record.养护人员 ?? '—' }}</td>
              <td>{{ record.疏通日期 ?? '—' }}</td>
              <td><span class="badge" :class="stageClass(record.stage)">{{ record.stage }}</span></td>
              <td>{{ record.复核人 ?? '—' }}</td>
              <td class="row-actions">
                <template v-if="record.stage === '待疏通'">
                  <button class="link" type="button" @click="openDateDialog(record)">登记疏通日期</button>
                </template>
                <template v-else-if="record.stage === '疏通中'">
                  <button class="link" type="button" @click="openDateDialog(record)">改疏通日期</button>
                  <button class="link" type="button" @click="openReview(record)">复核</button>
                </template>
                <span v-else class="locked-text">已复核，日期已锁定</span>
              </td>
            </tr>
            <tr v-if="!(detail.疏通记录 ?? []).length">
              <td colspan="8" class="empty-state">暂无疏通记录，可通过「补录疏通记录」登记</td>
            </tr>
          </tbody>
        </table>

        <div class="modal-actions">
          <span v-if="detailError" class="error-text">{{ detailError }}</span>
          <button class="btn" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>

    <!-- 登记 / 修改疏通日期 -->
    <div v-if="dateDialog.record" class="modal-mask" @click.self="closeDateDialog">
      <div class="modal modal-narrow">
        <h3>登记疏通日期 · 记录 #{{ dateDialog.record.id }}（{{ dateDialog.record.设施编号 }}）</h3>
        <p class="modal-tip">日期只落在该记录自身的设施编号上，提交后进度更新为「疏通中」。</p>
        <label class="form-item">
          <span>疏通日期</span>
          <input v-model="dateDialog.疏通日期" type="date" />
        </label>
        <label class="form-item">
          <span>养护人员</span>
          <input v-model="dateDialog.养护人员" placeholder="疏通队伍负责人" />
        </label>
        <div class="modal-actions">
          <span v-if="dateDialog.error" class="error-text">{{ dateDialog.error }}</span>
          <button class="btn ghost" type="button" @click="closeDateDialog">取消</button>
          <button class="btn primary" type="button" :disabled="dateDialog.submitting" @click="submitDate">提交</button>
        </div>
      </div>
    </div>

    <!-- 复核弹窗：进度与列表页、详情页同源 -->
    <div v-if="reviewDialog.record" class="modal-mask" @click.self="closeReview">
      <div class="modal modal-narrow">
        <h3>复核疏通记录 · 记录 #{{ reviewDialog.record.id }}</h3>
        <div class="detail-grid">
          <div><span class="detail-label">设施编号</span>{{ reviewDialog.record.设施编号 }}</div>
          <div><span class="detail-label">管径规格</span>{{ reviewDialog.record.管径规格 ?? '—' }}</div>
          <div><span class="detail-label">淤积深度</span>{{ reviewDialog.record.淤积深度 ?? '—' }}</div>
          <div><span class="detail-label">养护人员</span>{{ reviewDialog.record.养护人员 ?? '—' }}</div>
          <div><span class="detail-label">疏通日期</span>{{ reviewDialog.record.疏通日期 ?? '—' }}</div>
          <div>
            <span class="detail-label">当前进度</span>
            <span class="badge" :class="stageClass(reviewDialog.record.stage)">{{ reviewDialog.record.stage }}</span>
          </div>
        </div>
        <label class="form-item">
          <span>复核人</span>
          <input v-model="reviewDialog.复核人" placeholder="默认为值班复核员" />
        </label>
        <p class="modal-tip">复核通过后记录进入「已复核」，疏通日期随记录保留并锁定，不允许再修改。</p>
        <div class="modal-actions">
          <span v-if="reviewDialog.error" class="error-text">{{ reviewDialog.error }}</span>
          <button class="btn ghost" type="button" @click="closeReview">取消</button>
          <button class="btn primary" type="button" :disabled="reviewDialog.submitting" @click="submitReview">确认复核</button>
        </div>
      </div>
    </div>

    <!-- 批量补录：每条独立校验，失败的可只重试这一条 -->
    <div v-if="importDialog.open" class="modal-mask" @click.self="closeImport">
      <div class="modal modal-wide">
        <h3>补录疏通记录</h3>
        <p class="modal-tip">管径规格为空或设施编号不存在的记录会被阻断并说明原因；失败的行可单独重试，不影响已成功的行。</p>
        <table class="data-table">
          <thead>
            <tr>
              <th>设施编号</th>
              <th>管径规格</th>
              <th>淤积深度</th>
              <th>养护人员</th>
              <th>疏通日期</th>
              <th>结果</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in importDialog.items" :key="index" :class="{ 'row-fail': item.status === 'fail', 'row-ok': item.status === 'ok' }">
              <td><input v-model="item.设施编号" :disabled="item.status === 'ok'" placeholder="如 DRAI-0001" /></td>
              <td><input v-model="item.管径规格" :disabled="item.status === 'ok'" placeholder="如 DN600" /></td>
              <td><input v-model="item.淤积深度" :disabled="item.status === 'ok'" placeholder="如 0.20m" /></td>
              <td><input v-model="item.养护人员" :disabled="item.status === 'ok'" /></td>
              <td><input v-model="item.疏通日期" :disabled="item.status === 'ok'" type="date" /></td>
              <td>
                <span v-if="item.status === 'ok'" class="ok-text">已登记</span>
                <span v-else-if="item.status === 'fail'" class="error-text">{{ item.message }}</span>
                <span v-else class="muted-text">待提交</span>
              </td>
              <td class="row-actions">
                <button v-if="item.status === 'fail'" class="link" type="button" :disabled="item.retrying" @click="retryImportRow(item)">
                  {{ item.retrying ? '重试中…' : '重试' }}
                </button>
                <button v-if="item.status !== 'ok'" class="link" type="button" @click="removeImportRow(index)">移除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="addImportRow">添加一行</button>
          <span v-if="importDialog.message" class="error-text">{{ importDialog.message }}</span>
          <button class="btn" type="button" @click="closeImport">关闭</button>
          <button class="btn primary" type="button" :disabled="importDialog.submitting" @click="submitImport">
            {{ importDialog.submitting ? '提交中…' : '提交补录' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 登记排水设施 -->
    <div v-if="createDialog.open" class="modal-mask" @click.self="closeCreate">
      <div class="modal modal-narrow">
        <h3>登记排水设施</h3>
        <label v-for="field in createFields" :key="field" class="form-item">
          <span>{{ field }}</span>
          <input v-model="createDialog.values[field]" :placeholder="`请输入${field}`" />
        </label>
        <div class="modal-actions">
          <span v-if="createDialog.error" class="error-text">{{ createDialog.error }}</span>
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="button" :disabled="createDialog.submitting" @click="submitCreate">提交</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

interface FlowRecord {
  id: number
  stage: string
  设施编号: string
  管径规格: string | null
  淤积深度: string | null
  养护人员: string | null
  疏通日期: string | null
  复核人: string | null
  复核时间: string | null
  备注: string | null
}

interface Facility {
  id: number
  设施编号: string
  设施类型: string | null
  所在路段: string | null
  管径规格: string | null
  淤积深度: string | null
  排水状态: string | null
  疏通进度: string
  最新疏通日期: string | null
  养护人员: string | null
  疏通记录?: FlowRecord[]
  [key: string]: unknown
}

interface ImportRow {
  设施编号: string
  管径规格: string
  淤积深度: string
  养护人员: string
  疏通日期: string
  status: 'idle' | 'ok' | 'fail'
  message: string
  retrying: boolean
}

const ENDPOINT = '/api/drain'
const columns = ['设施编号', '设施类型', '所在路段', '管径规格', '淤积深度', '最新疏通日期', '养护人员', '疏通进度']
const stages = ['待疏通', '疏通中', '已复核']
const createFields = ['设施编号', '设施类型', '所在路段', '管径规格', '淤积深度']

const rows = ref<Facility[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref({ keyword: '', stage: '' })
const summary = ref<Record<string, number>>({ 待疏通: 0, 疏通中: 0, 已复核: 0 })

const stats = computed(() => stages.map((stage) => ({ label: `${stage}记录`, value: summary.value[stage] ?? 0 })))

const detail = ref<Facility | null>(null)
const detailError = ref('')

const dateDialog = ref<{ record: FlowRecord | null; 疏通日期: string; 养护人员: string; error: string; submitting: boolean }>({
  record: null,
  疏通日期: '',
  养护人员: '',
  error: '',
  submitting: false,
})

const reviewDialog = ref<{ record: FlowRecord | null; 复核人: string; error: string; submitting: boolean }>({
  record: null,
  复核人: '',
  error: '',
  submitting: false,
})

const importDialog = ref<{ open: boolean; items: ImportRow[]; message: string; submitting: boolean }>({
  open: false,
  items: [],
  message: '',
  submitting: false,
})

const createDialog = ref<{ open: boolean; values: Record<string, string>; error: string; submitting: boolean }>({
  open: false,
  values: {},
  error: '',
  submitting: false,
})

function stageClass(stage: unknown) {
  return {
    pending: stage === '待疏通',
    doing: stage === '疏通中',
    done: stage === '已复核',
    none: stage === '未登记',
  }
}

async function readPayload(response: Response): Promise<{ ok: boolean; message?: string } & Record<string, unknown>> {
  return (await response.json()) as { ok: boolean; message?: string } & Record<string, unknown>
}

function resetFilters() {
  filters.value = { keyword: '', stage: '' }
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.value.keyword) query.set('keyword', filters.value.keyword)
  if (filters.value.stage) query.set('stage', filters.value.stage)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) throw new Error('排水设施列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水设施列表读取失败'
  }
}

async function loadSummary() {
  try {
    const response = await request(`${ENDPOINT}/summary`)
    if (!response.ok) return
    const payload = await response.json()
    summary.value = payload.stages ?? summary.value
  } catch {
    /* 统计卡片失败不阻塞列表 */
  }
}

async function refreshAll() {
  await Promise.all([reload(), loadSummary()])
  if (detail.value) {
    const response = await request(`${ENDPOINT}/${detail.value.id}`)
    if (response.ok) detail.value = await response.json()
  }
}

async function openDetail(row: Facility) {
  detailError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error('排水设施详情读取失败')
    detail.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水设施详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
}

function openDateDialog(record: FlowRecord) {
  dateDialog.value = {
    record,
    疏通日期: record.疏通日期 ?? '',
    养护人员: record.养护人员 ?? '',
    error: '',
    submitting: false,
  }
}

function closeDateDialog() {
  dateDialog.value.record = null
}

async function submitDate() {
  const dialog = dateDialog.value
  if (!dialog.record) return
  dialog.error = ''
  dialog.submitting = true
  try {
    const response = await request(`${ENDPOINT}/flow/${dialog.record.id}/date`, {
      method: 'POST',
      body: JSON.stringify({ values: { 疏通日期: dialog.疏通日期, 养护人员: dialog.养护人员 } }),
    })
    const payload = await readPayload(response)
    if (!payload.ok) throw new Error(payload.message ?? '疏通日期登记失败')
    closeDateDialog()
    await refreshAll()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '疏通日期登记失败'
  } finally {
    dialog.submitting = false
  }
}

function openReview(record: FlowRecord) {
  reviewDialog.value = { record, 复核人: '', error: '', submitting: false }
}

function closeReview() {
  reviewDialog.value.record = null
}

async function submitReview() {
  const dialog = reviewDialog.value
  if (!dialog.record) return
  dialog.error = ''
  dialog.submitting = true
  try {
    const response = await request(`${ENDPOINT}/flow/${dialog.record.id}/review`, {
      method: 'POST',
      body: JSON.stringify({ values: { 复核人: dialog.复核人 } }),
    })
    const payload = await readPayload(response)
    if (!payload.ok) throw new Error(payload.message ?? '复核失败')
    closeReview()
    await refreshAll()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '复核失败'
  } finally {
    dialog.submitting = false
  }
}

function emptyImportRow(): ImportRow {
  return { 设施编号: '', 管径规格: '', 淤积深度: '', 养护人员: '', 疏通日期: '', status: 'idle', message: '', retrying: false }
}

function openImport() {
  importDialog.value = { open: true, items: [emptyImportRow()], message: '', submitting: false }
}

function closeImport() {
  importDialog.value.open = false
}

function addImportRow() {
  importDialog.value.items.push(emptyImportRow())
}

function removeImportRow(index: number) {
  importDialog.value.items.splice(index, 1)
}

function importValues(item: ImportRow) {
  return {
    设施编号: item.设施编号,
    管径规格: item.管径规格,
    淤积深度: item.淤积深度,
    养护人员: item.养护人员,
    疏通日期: item.疏通日期,
  }
}

async function submitImport() {
  const dialog = importDialog.value
  dialog.message = ''
  const pending = dialog.items.filter((item) => item.status !== 'ok')
  if (!pending.length) {
    dialog.message = '没有待提交的补录记录'
    return
  }
  dialog.submitting = true
  try {
    const response = await request(`${ENDPOINT}/flow/import`, {
      method: 'POST',
      body: JSON.stringify({ items: pending.map(importValues) }),
    })
    const payload = await response.json()
    const results = (payload.results ?? []) as Array<{ index: number; ok: boolean; message: string }>
    for (const result of results) {
      const item = pending[result.index]
      if (!item) continue
      item.status = result.ok ? 'ok' : 'fail'
      item.message = result.ok ? '' : result.message
    }
    dialog.message = payload.message ?? ''
    await refreshAll()
  } catch (error) {
    dialog.message = error instanceof Error ? error.message : '补录提交失败'
  } finally {
    dialog.submitting = false
  }
}

async function retryImportRow(item: ImportRow) {
  item.retrying = true
  item.message = ''
  try {
    const response = await request(`${ENDPOINT}/flow`, {
      method: 'POST',
      body: JSON.stringify({ values: importValues(item) }),
    })
    const payload = await readPayload(response)
    if (!payload.ok) throw new Error(payload.message ?? '补录失败')
    item.status = 'ok'
    await refreshAll()
  } catch (error) {
    item.status = 'fail'
    item.message = error instanceof Error ? error.message : '补录失败'
  } finally {
    item.retrying = false
  }
}

function openCreate() {
  createDialog.value = { open: true, values: {}, error: '', submitting: false }
}

function closeCreate() {
  createDialog.value.open = false
}

async function submitCreate() {
  const dialog = createDialog.value
  dialog.error = ''
  dialog.submitting = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: dialog.values }),
    })
    const payload = await readPayload(response)
    if (!payload.ok) throw new Error(payload.message ?? '排水设施登记失败')
    closeCreate()
    await refreshAll()
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '排水设施登记失败'
  } finally {
    dialog.submitting = false
  }
}

onMounted(refreshAll)
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
}
.modal {
  background: #fff;
  border-radius: 10px;
  padding: 16px 20px;
  width: 760px;
  max-width: calc(100vw - 48px);
  max-height: 84vh;
  overflow: auto;
}
.modal-narrow {
  width: 460px;
}
.modal-wide {
  width: 960px;
}
.modal h3 {
  margin: 0 0 10px;
  font-size: 15px;
}
.modal-subtitle {
  margin: 14px 0 8px;
  font-size: 13px;
}
.modal-tip {
  color: var(--muted);
  font-size: 12px;
  margin: 8px 0;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px 16px;
  font-size: 13px;
}
.detail-label {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.form-item {
  display: block;
  margin-bottom: 10px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 2px;
}
.form-item input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
}
.badge.pending {
  background: #fef3c7;
  color: #92400e;
}
.badge.doing {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge.done {
  background: #dcfce7;
  color: #166534;
}
.badge.none {
  background: #f1f5f9;
  color: #64748b;
}
.locked-text {
  color: var(--muted);
  font-size: 12px;
}
.ok-text {
  color: #166534;
  font-size: 12px;
}
.muted-text {
  color: var(--muted);
  font-size: 12px;
}
.row-fail {
  background: #fef2f2;
}
.row-ok {
  background: #f0fdf4;
}
.data-table input {
  width: 100%;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: 13px;
}
</style>

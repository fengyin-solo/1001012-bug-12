<template>
  <section class="page" data-module="drain">
    <header class="page-head">
      <div>
        <h2>排水设施管理</h2>
        <p class="page-desc">
          设施台账、疏通登记、复核三段数据分开存放；疏通日期只落在对应设施编号上，
          已复核记录不可再改疏通日期，历史疏通记录只追加不覆盖。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openRegisterFacility">登记排水设施</button>
        <button class="btn" type="button" @click="openBatch">疏通登记</button>
        <button class="btn" type="button" @click="openBackfill">历史疏通补录</button>
        <button class="btn" type="button" @click="exportRows">导出清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>设施编号</span>
        <input v-model="keyword" placeholder="按设施编号检索" />
      </label>
      <label class="filter-item">
        <span>进度</span>
        <select v-model="progressFilter">
          <option value="">全部进度</option>
          <option v-for="status in progressOrder" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <span v-if="column === '进度'">
              <span class="badge" :class="badgeClass(row.进度)">{{ row.进度 }}</span>
            </span>
            <span v-else>{{ display(row, column) }}</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-if="row.进度 === '待疏通'"
              class="link"
              type="button"
              @click="openDredgeFor(row)"
            >
              登记疏通

            </button>
            <template v-else-if="row.进度 === '疏通中'">
              <button class="link" type="button" @click="openEdit(row)">改疏通日期</button>
              <button class="link" type="button" @click="openReview(row)">复核</button>
            </template>
            <button
              v-else
              class="link"
              type="button"
              :title="'上一轮已复核，可登记新一轮疏通，历史记录保留'"
              @click="openDredgeFor(row)"
            >
              新一轮疏通
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无符合条件的排水设施</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条排水设施记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <!-- 设施台账登记 -->
    <div v-if="facilityModal.show" class="modal-mask" @click.self="facilityModal.show = false">
      <div class="modal">
        <div class="modal-head">
          <h3>登记排水设施</h3>
          <button class="modal-close" type="button" @click="facilityModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-grid">
            <label v-for="field in facilityFields" :key="field.name" class="form-field" :class="{ full: field.full }">
              <span>{{ field.label }}<i v-if="field.required" class="req">*</i></span>
              <input v-model="facilityModal.form[field.name]" :placeholder="`请填写${field.label}`" />
            </label>
          </div>
          <p v-if="facilityModal.error" class="field-error">{{ facilityModal.error }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="facilityModal.show = false">取消</button>
          <button class="btn primary" type="button" @click="submitFacility">提交登记</button>
        </div>
      </div>
    </div>

    <!-- 疏通登记（批量，整批预检） -->
    <div v-if="batchModal.show" class="modal-mask" @click.self="batchModal.show = false">
      <div class="modal wide">
        <div class="modal-head">
          <h3>疏通队伍登记疏通日期</h3>
          <button class="modal-close" type="button" @click="batchModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <p class="modal-tip">
            疏通日期、养护人员会按设施编号单独追加到疏通登记表；存在被阻断的编号时整批不落库，
            阻断编号与原因在下方一并列出。
          </p>
          <table class="editor-table">
            <thead>
              <tr>
                <th style="width: 150px">设施编号*</th>
                <th style="width: 150px">疏通日期*</th>
                <th style="width: 110px">养护人员</th>
                <th>疏通队伍</th>
                <th style="width: 48px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in batchModal.items" :key="index">
                <td><input v-model="item.设施编号" :disabled="item.locked" placeholder="如 DRAI-0001" /></td>
                <td><input v-model="item.疏通日期" type="date" /></td>
                <td><input v-model="item.养护人员" /></td>
                <td><input v-model="item.疏通队伍" /></td>
                <td>
                  <button class="link" type="button" @click="removeBatchRow(index)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div style="margin-top: 8px">
            <button class="btn small" type="button" @click="addBatchRow()">+ 增加一条</button>
          </div>
          <div v-if="batchModal.blocked.length" class="block-list">
            <strong>以下设施编号被阻断，整批未提交，请修正后重新提交：</strong>
            <ul>
              <li v-for="(reason, i) in batchModal.blocked" :key="i">{{ reason }}</li>
            </ul>
          </div>
          <p v-if="batchModal.error" class="field-error">{{ batchModal.error }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="batchModal.show = false">关闭</button>
          <button class="btn primary" type="button" @click="submitBatch">整批提交</button>
        </div>
      </div>
    </div>

    <!-- 复核弹窗：进度与列表、详情取同一份数据 -->
    <div v-if="reviewModal.show && reviewModal.row" class="modal-mask" @click.self="reviewModal.show = false">
      <div class="modal">
        <div class="modal-head">
          <h3>疏通复核</h3>
          <button class="modal-close" type="button" @click="reviewModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-head">
            <strong>{{ reviewModal.row.设施编号 }}</strong>
            <span class="badge" :class="badgeClass(reviewModal.row.进度)">{{ reviewModal.row.进度 }}</span>
            <span class="modal-tip" style="margin: 0">登记淤积深度 {{ reviewModal.row.淤积深度 || '—' }}</span>
          </div>
          <div class="form-grid">
            <label class="form-field">
              <span>疏通日期（只读）</span>
              <input :value="reviewModal.row.疏通日期" readonly />
            </label>
            <label class="form-field">
              <span>养护人员（只读）</span>
              <input :value="reviewModal.row.养护人员" readonly />
            </label>
            <label class="form-field">
              <span>复核日期*</span>
              <input v-model="reviewModal.form.复核日期" type="date" />
            </label>
            <label class="form-field">
              <span>复核人*</span>
              <input v-model="reviewModal.form.复核人" placeholder="请填写复核人" />
            </label>
            <label class="form-field">
              <span>复核结果*</span>
              <select v-model="reviewModal.form.复核结果">
                <option value="合格">合格</option>
                <option value="不合格">不合格</option>
              </select>
            </label>
          </div>
          <p v-if="reviewModal.error" class="field-error">{{ reviewModal.error }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="reviewModal.show = false">取消</button>
          <button class="btn primary" type="button" @click="submitReview">通过复核</button>
        </div>
      </div>
    </div>

    <!-- 修改疏通日期（仅未复核） -->
    <div v-if="editModal.show && editModal.row" class="modal-mask" @click.self="editModal.show = false">
      <div class="modal">
        <div class="modal-head">
          <h3>修改疏通信息</h3>
          <button class="modal-close" type="button" @click="editModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <div class="detail-head">
            <strong>{{ editModal.row.设施编号 }}</strong>
            <span class="badge" :class="badgeClass(editModal.row.进度)">{{ editModal.row.进度 }}</span>
          </div>
          <div class="form-grid">
            <label class="form-field">
              <span>设施编号（只读）</span>
              <input :value="editModal.row.设施编号" readonly />
            </label>
            <label class="form-field">
              <span>登记时淤积深度（只读）</span>
              <input :value="editModal.row.淤积深度" readonly />
            </label>
            <label class="form-field">
              <span>疏通日期*</span>
              <input v-model="editModal.form.疏通日期" type="date" />
            </label>
            <label class="form-field">
              <span>养护人员</span>
              <input v-model="editModal.form.养护人员" />
            </label>
            <label class="form-field full">
              <span>疏通队伍</span>
              <input v-model="editModal.form.疏通队伍" />
            </label>
          </div>
          <p v-if="editModal.error" class="field-error">{{ editModal.error }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="editModal.show = false">取消</button>
          <button class="btn primary" type="button" @click="submitEdit">保存修改</button>
        </div>
      </div>
    </div>

    <!-- 历史疏通补录：逐条独立，失败可只重试这一条 -->
    <div v-if="backfillModal.show" class="modal-mask" @click.self="backfillModal.show = false">
      <div class="modal wide">
        <div class="modal-head">
          <h3>历史疏通记录补录</h3>
          <button class="modal-close" type="button" @click="backfillModal.show = false">×</button>
        </div>
        <div class="modal-body">
          <p class="modal-tip">
            补录按条独立提交，一条失败不影响其他条；失败的条目保留在表格里，可只重试这一条。
            补录记录只进历史，不会覆盖当前疏通周期。
          </p>
          <table class="editor-table">
            <thead>
              <tr>
                <th style="width: 140px">设施编号*</th>
                <th style="width: 145px">疏通日期*</th>
                <th style="width: 100px">养护人员*</th>
                <th>疏通队伍</th>
                <th style="width: 140px">状态 / 原因</th>
                <th style="width: 72px">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in backfillModal.items"
                :key="index"
                :class="item.status === 'fail' ? 'row-fail' : item.status === 'ok' ? 'row-ok' : ''"
              >
                <td><input v-model="item.设施编号" :disabled="item.status === 'ok'" /></td>
                <td><input v-model="item.疏通日期" type="date" :disabled="item.status === 'ok'" /></td>
                <td><input v-model="item.养护人员" :disabled="item.status === 'ok'" /></td>
                <td><input v-model="item.疏通队伍" :disabled="item.status === 'ok'" /></td>
                <td class="row-state" :class="item.status === 'fail' ? 'fail' : item.status === 'ok' ? 'ok' : ''">
                  <template v-if="item.status === 'ok'">已补录 ✓</template>
                  <template v-else-if="item.status === 'fail'">
                    被阻断：{{ item.reason }}
                  </template>
                  <template v-else>待提交</template>
                </td>
                <td>
                  <button
                    v-if="item.status === 'fail'"
                    class="link"
                    type="button"
                    @click="retryBackfillRow(index)"
                  >
                    重试本条
                  </button>
                  <button v-else-if="item.status !== 'ok'" class="link" type="button" @click="removeBackfillRow(index)">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
          <div style="margin-top: 8px; display: flex; gap: 8px">
            <button class="btn small" type="button" @click="addBackfillRow()">+ 增加一条</button>
            <button
              v-if="backfillFailCount > 0"
              class="btn small"
              type="button"
              @click="retryBackfillFailed"
            >
              只重试失败的 {{ backfillFailCount }} 条
            </button>
          </div>
          <p v-if="backfillModal.error" class="field-error">{{ backfillModal.error }}</p>
        </div>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="backfillModal.show = false">关闭</button>
          <button class="btn primary" type="button" @click="submitBackfill">提交补录</button>
        </div>
      </div>
    </div>

    <!-- 设施详情：进度与列表、复核弹窗同源 -->
    <div v-if="detailModal.show && detailModal.row" class="modal-mask" @click.self="detailModal.show = false">
      <div class="modal wide">
        <div class="modal-head">
          <h3>排水设施详情</h3>
          <button class="modal-close" type="button" @click="detailModal.show = false">×</button>
        </div>
        <div class="modal-body" v-if="detailModal.loading">
          <p class="modal-tip">正在读取详情…</p>
        </div>
        <div class="modal-body" v-else>
          <div class="detail-head">
            <h3>{{ detailModal.row.设施编号 }}</h3>
            <span class="badge" :class="badgeClass(detailModal.row.进度)">{{ detailModal.row.进度 }}</span>
            <button
              v-if="detailModal.row.进度 === '疏通中'"
              class="btn small primary"
              type="button"
              @click="openReview(detailModal.row)"
            >
              去复核
            </button>
          </div>
          <dl class="detail-grid">
            <div><dt>设施类型</dt><dd>{{ detailModal.row.设施类型 || '—' }}</dd></div>
            <div><dt>所在路段</dt><dd>{{ detailModal.row.所在路段 || '—' }}</dd></div>
            <div><dt>管径规格</dt><dd>{{ detailModal.row.管径规格 || '—' }}</dd></div>
            <div><dt>当前淤积深度</dt><dd>{{ detailModal.row.淤积深度 || '—' }}</dd></div>
            <div><dt>本轮疏通日期</dt><dd>{{ detailModal.row.疏通日期 || '—' }}</dd></div>
            <div><dt>本轮养护人员</dt><dd>{{ detailModal.row.养护人员 || '—' }}</dd></div>
            <div><dt>疏通队伍</dt><dd>{{ detailModal.row.疏通队伍 || '—' }}</dd></div>
            <div><dt>复核日期</dt><dd>{{ detailModal.row.复核日期 || '—' }}</dd></div>
            <div><dt>复核人 / 结果</dt>
              <dd>{{ detailModal.row.复核人 || '—' }}<template v-if="detailModal.row.复核结果"> / {{ detailModal.row.复核结果 }}</template></dd>
            </div>
          </dl>

          <div class="section-title">
            <span>历史疏通记录（只追加，新增不会覆盖）</span>
            <button class="btn small" type="button" @click="openBackfill">补录历史</button>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>疏通日期</th>
                <th>养护人员</th>
                <th>疏通队伍</th>
                <th>当时淤积深度</th>
                <th>复核日期</th>
                <th>复核人</th>
                <th>复核结果</th>
                <th>来源</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="rec in detailModal.row.疏通记录" :key="rec.record_id">
                <td>{{ rec.疏通日期 || '—' }}</td>
                <td>{{ rec.养护人员 || '—' }}</td>
                <td>{{ rec.疏通队伍 || '—' }}</td>
                <td>{{ rec.登记时淤积深度 || '—' }}</td>
                <td>{{ rec.复核日期 || '—' }}</td>
                <td>{{ rec.复核人 || '—' }}</td>
                <td>{{ rec.复核结果 || '未复核' }}</td>
                <td>
                  {{ rec.历史补录 ? '历史补录' : '正常登记' }}
                  <span v-if="rec.record_id === detailModal.row.active_record_id" class="tag">当前周期</span>
                </td>
              </tr>
              <tr v-if="!detailModal.row.疏通记录.length">
                <td colspan="8" class="empty-state">暂无疏通记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Progress = '待疏通' | '疏通中' | '已复核'

interface HistoryRecord {
  record_id: number
  疏通日期: string
  养护人员: string
  疏通队伍: string
  登记时淤积深度: string
  登记时间: string
  历史补录: boolean
  复核日期: string
  复核人: string
  复核结果: string
}

interface FacilityRow {
  [key: string]: string | number | null | HistoryRecord[]
  id: number
  设施编号: string
  设施类型: string
  所在路段: string
  管径规格: string
  淤积深度: string
  疏通日期: string
  养护人员: string
  疏通队伍: string
  复核日期: string
  复核人: string
  复核结果: string
  进度: Progress
  active_record_id: number | null
  历史条数: number
  疏通记录: HistoryRecord[]
}

const ENDPOINT = '/api/drain'
const columns = ['设施编号', '设施类型', '所在路段', '管径规格', '淤积深度', '疏通日期', '养护人员', '进度']
const progressOrder: Progress[] = ['待疏通', '疏通中', '已复核']

const rows = ref<FacilityRow[]>([])
const total = ref(0)
const keyword = ref('')
const progressFilter = ref('')
const statsMap = ref<Record<Progress, number>>({ 待疏通: 0, 疏通中: 0, 已复核: 0 })
const errorMessage = ref('')
const successMessage = ref('')
let noticeTimer: ReturnType<typeof setTimeout> | undefined

const statCards = computed(() => [
  { label: '待疏通设施', value: statsMap.value['待疏通'] },
  { label: '疏通中设施', value: statsMap.value['疏通中'] },
  { label: '已复核设施', value: statsMap.value['已复核'] },
])

function notice(message: string, ok = true) {
  successMessage.value = ok ? message : ''
  errorMessage.value = ok ? '' : message
  clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => {
    successMessage.value = ''
    errorMessage.value = ''
  }, 4000)
}

function badgeClass(progress: string): string {
  if (progress === '疏通中') return 'doing'
  if (progress === '已复核') return 'reviewed'
  return 'pending'
}

function display(row: FacilityRow, column: string): string {
  const value = row[column]
  if (Array.isArray(value)) return '—'
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function resetFilters() {
  keyword.value = ''
  progressFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (progressFilter.value) query.set('progress', progressFilter.value)
  try {
    const [listRes, statsRes] = await Promise.all([
      request(`${ENDPOINT}?${query.toString()}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listRes.ok) throw new Error('排水设施列表读取失败')
    const payload = await listRes.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (statsRes.ok) {
      const statsPayload = await statsRes.json()
      statsMap.value = { 待疏通: 0, 疏通中: 0, 已复核: 0, ...(statsPayload.stats ?? {}) }
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '排水设施列表读取失败'
  }
}

function apiError(payload: { message?: string } | null, fallback: string): string {
  return payload?.message || fallback
}

// ---- 设施台账登记 ----------------------------------------------------------

const facilityFields: { name: string; label: string; required?: boolean; full?: boolean }[] = [
  { name: '设施编号', label: '设施编号', required: true },
  { name: '设施类型', label: '设施类型', required: true },
  { name: '所在路段', label: '所在路段', required: true },
  { name: '管径规格', label: '管径规格', required: true },
  { name: '淤积深度', label: '淤积深度', required: false, full: true },
]

const emptyFacilityForm = (): Record<string, string> => ({
  设施编号: '',
  设施类型: '',
  所在路段: '',
  管径规格: '',
  淤积深度: '',
})

const facilityModal = reactive({
  show: false,
  form: emptyFacilityForm(),
  error: '',
})

function openRegisterFacility() {
  facilityModal.form = emptyFacilityForm()
  facilityModal.error = ''
  facilityModal.show = true
}

async function submitFacility() {
  facilityModal.error = ''
  try {
    const res = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...facilityModal.form } }),
    })
    const payload = await res.json()
    if (!res.ok || !payload.ok) {
      facilityModal.error = apiError(payload, '登记失败，请检查必填项')
      return
    }
    facilityModal.show = false
    notice('排水设施已登记')
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    facilityModal.error = error instanceof Error ? error.message : '登记失败'
  }
}

// ---- 疏通登记（批量） -------------------------------------------------------

interface BatchItem {
  设施编号: string
  疏通日期: string
  养护人员: string
  疏通队伍: string
  locked?: boolean
}

const batchModal = reactive<{
  show: boolean
  items: BatchItem[]
  blocked: string[]
  error: string
}>({
  show: false,
  items: [],
  blocked: [],
  error: '',
})

function addBatchRow(prefill?: Partial<BatchItem>) {
  batchModal.items.push({
    设施编号: '',
    疏通日期: '',
    养护人员: '',
    疏通队伍: '',
    ...prefill,
  })
}

function removeBatchRow(index: number) {
  batchModal.items.splice(index, 1)
}

function openBatch() {
  batchModal.items = []
  batchModal.blocked = []
  batchModal.error = ''
  addBatchRow()
  batchModal.show = true
}

function openDredgeFor(row: FacilityRow) {
  batchModal.items = []
  batchModal.blocked = []
  batchModal.error = ''
  addBatchRow({ 设施编号: row.设施编号, locked: true })
  batchModal.show = true
}

async function submitBatch() {
  batchModal.blocked = []
  batchModal.error = ''
  const items = batchModal.items.map(({ locked: _locked, ...item }) => item)
  if (!items.some((item) => item.设施编号.trim())) {
    batchModal.error = '请至少填写一行疏通登记'
    return
  }
  try {
    const res = await request(`${ENDPOINT}/dredge`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    })
    const payload = await res.json()
    if (!res.ok || !payload.ok) {
      // 整批被阻断：编号与原因原样列出，行数据保留供修改后重提
      batchModal.blocked = payload.blocked ?? []
      batchModal.error = apiError(payload, '疏通登记未提交')
      return
    }
    batchModal.show = false
    notice(apiError(payload, `已登记 ${payload.entries?.length ?? 0} 条疏通记录`))
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    batchModal.error = error instanceof Error ? error.message : '疏通登记提交失败'
  }
}

// ---- 复核 ------------------------------------------------------------------

const reviewModal = reactive<{
  show: boolean
  row: FacilityRow | null
  form: { 复核日期: string; 复核人: string; 复核结果: string }
  error: string
}>({
  show: false,
  row: null,
  form: { 复核日期: '', 复核人: '', 复核结果: '合格' },
  error: '',
})

function openReview(row: FacilityRow) {
  reviewModal.row = row
  reviewModal.form = {
    复核日期: row.复核日期 || new Date().toISOString().slice(0, 10),
    复核人: row.复核人 || '',
    复核结果: (row.复核结果 as '合格' | '不合格') || '合格',
  }
  reviewModal.error = ''
  reviewModal.show = true
}

async function submitReview() {
  if (!reviewModal.row?.active_record_id) {
    reviewModal.error = '该设施没有可复核的疏通登记'
    return
  }
  reviewModal.error = ''
  try {
    const res = await request(`${ENDPOINT}/records/${reviewModal.row.active_record_id}/review`, {
      method: 'POST',
      body: JSON.stringify({ values: { ...reviewModal.form } }),
    })
    const payload = await res.json()
    if (!res.ok || !payload.ok) {
      reviewModal.error = apiError(payload, '复核未通过')
      return
    }
    reviewModal.show = false
    notice('疏通记录已复核，进度已更新为已复核')
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    reviewModal.error = error instanceof Error ? error.message : '复核提交失败'
  }
}

// ---- 修改疏通日期 ------------------------------------------------------------

const editModal = reactive<{
  show: boolean
  row: FacilityRow | null
  form: { 疏通日期: string; 养护人员: string; 疏通队伍: string }
  error: string
}>({
  show: false,
  row: null,
  form: { 疏通日期: '', 养护人员: '', 疏通队伍: '' },
  error: '',
})

function openEdit(row: FacilityRow) {
  editModal.row = row
  editModal.form = {
    疏通日期: row.疏通日期 || '',
    养护人员: row.养护人员 || '',
    疏通队伍: row.疏通队伍 || '',
  }
  editModal.error = ''
  editModal.show = true
}

async function submitEdit() {
  if (!editModal.row?.active_record_id) {
    editModal.error = '该设施没有可修改的疏通登记'
    return
  }
  editModal.error = ''
  try {
    const res = await request(`${ENDPOINT}/records/${editModal.row.active_record_id}`, {
      method: 'PATCH',
      body: JSON.stringify({ values: { ...editModal.form } }),
    })
    const payload = await res.json()
    if (!res.ok || !payload.ok) {
      editModal.error = apiError(payload, '修改未生效')
      return
    }
    editModal.show = false
    notice('疏通信息已更新')
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    editModal.error = error instanceof Error ? error.message : '修改失败'
  }
}

// ---- 历史补录（逐条独立，失败可单条重试） -------------------------------------

interface BackfillItem {
  设施编号: string
  疏通日期: string
  养护人员: string
  疏通队伍: string
  client_key: string
  status: '' | 'ok' | 'fail'
  reason: string
}

let backfillSeq = 0

function nextClientKey(): string {
  backfillSeq += 1
  return `bf-${Date.now()}-${backfillSeq}`
}

const backfillModal = reactive<{
  show: boolean
  items: BackfillItem[]
  error: string
}>({
  show: false,
  items: [],
  error: '',
})

const backfillFailCount = computed(() => backfillModal.items.filter((item) => item.status === 'fail').length)

function addBackfillRow() {
  backfillModal.items.push({
    设施编号: '',
    疏通日期: '',
    养护人员: '',
    疏通队伍: '',
    client_key: nextClientKey(),
    status: '',
    reason: '',
  })
}

function removeBackfillRow(index: number) {
  backfillModal.items.splice(index, 1)
}

function openBackfill() {
  backfillModal.items = []
  backfillModal.error = ''
  addBackfillRow()
  backfillModal.show = true
}

function toBackfillPayload(item: BackfillItem) {
  return {
    设施编号: item.设施编号,
    疏通日期: item.疏通日期,
    养护人员: item.养护人员,
    疏通队伍: item.疏通队伍,
    client_key: item.client_key,
  }
}

function markBackfillResult(item: BackfillItem, status: 'ok' | 'fail', reason = '') {
  item.status = status
  item.reason = reason
}

async function postBackfill(items: BackfillItem[]): Promise<{ ok: boolean; payload: any }> {
  const res = await request(`${ENDPOINT}/backfill`, {
    method: 'POST',
    body: JSON.stringify({ items: items.map(toBackfillPayload) }),
  })
  return { ok: res.ok, payload: await res.json() }
}

function matchBackfillItem(items: BackfillItem[], result: Record<string, unknown>): BackfillItem | undefined {
  // 优先按行内 client_key 精确匹配，避免同批次重复编号标错行
  const key = String(result.client_key ?? '')
  if (key) {
    const byKey = items.find((item) => item.client_key === key)
    if (byKey) return byKey
  }
  return items.find((item) => item.设施编号 === String(result.设施编号 ?? '') && item.status !== 'ok')
}

async function submitBackfill() {
  backfillModal.error = ''
  const pending = backfillModal.items.filter((item) => item.status !== 'ok')
  if (!pending.length) {
    backfillModal.error = '没有待提交的补录条目'
    return
  }
  try {
    const { ok, payload } = await postBackfill(pending)
    if (!payload) {
      backfillModal.error = '补录失败，请稍后重试'
      return
    }
    // 服务端逐条返回：成功的锁定，失败的保留原因，可只重试失败的这一条
    for (const failed of payload.failed ?? []) {
      const target = matchBackfillItem(pending, failed)
      if (target) markBackfillResult(target, 'fail', String(failed.reason ?? '补录被阻断'))
    }
    for (const succeeded of payload.succeeded ?? []) {
      const target = matchBackfillItem(pending, succeeded)
      if (target) markBackfillResult(target, 'ok')
    }
    notice(apiError(payload, '补录完成'), (payload.failed ?? []).length === 0)
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    backfillModal.error = error instanceof Error ? error.message : '补录请求失败'
  }
}

async function retryBackfillRow(index: number) {
  const item = backfillModal.items[index]
  if (!item || item.status !== 'fail') return
  backfillModal.error = ''
  try {
    const { payload } = await postBackfill([item])
    const failed = payload?.failed?.[0]
    if (failed) {
      markBackfillResult(item, 'fail', String(failed.reason ?? '补录被阻断'))
      return
    }
    if (payload?.succeeded?.length) markBackfillResult(item, 'ok')
    notice(apiError(payload, '该条补录成功'))
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    item.reason = error instanceof Error ? error.message : '请求失败'
  }
}

async function retryBackfillFailed() {
  const failedItems = backfillModal.items.filter((item) => item.status === 'fail')
  if (!failedItems.length) return
  backfillModal.error = ''
  try {
    const { payload } = await postBackfill(failedItems)
    for (const failed of payload?.failed ?? []) {
      const target = matchBackfillItem(failedItems, failed)
      if (target) markBackfillResult(target, 'fail', String(failed.reason ?? '补录被阻断'))
    }
    for (const succeeded of payload?.succeeded ?? []) {
      const target = matchBackfillItem(failedItems, succeeded)
      if (target) markBackfillResult(target, 'ok')
    }
    notice(apiError(payload, '失败条目已重试'))
    await reload()
    await refreshDetailIfOpen()
  } catch (error) {
    backfillModal.error = error instanceof Error ? error.message : '重试失败'
  }
}

// ---- 详情 -------------------------------------------------------------------

const detailModal = reactive<{
  show: boolean
  loading: boolean
  row: FacilityRow | null
}>({
  show: false,
  loading: false,
  row: null,
})

async function refreshDetailIfOpen() {
  if (!detailModal.show || !detailModal.row) return
  try {
    const res = await request(`${ENDPOINT}/${detailModal.row.id}`)
    if (res.ok) detailModal.row = await res.json()
  } catch {
    // 详情刷新失败不阻断主流程，下次打开会重新拉取
  }
}

async function openDetail(row: FacilityRow) {
  detailModal.show = true
  detailModal.loading = true
  detailModal.row = row
  try {
    const res = await request(`${ENDPOINT}/${row.id}`)
    if (!res.ok) throw new Error('设施详情读取失败')
    detailModal.row = await res.json()
  } catch (error) {
    notice(error instanceof Error ? error.message : '设施详情读取失败', false)
    detailModal.show = false
  } finally {
    detailModal.loading = false
  }
}

onMounted(reload)
</script>

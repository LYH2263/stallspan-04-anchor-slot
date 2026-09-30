<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const savedId = ref<number | null>(null)
const savedTimer = ref<number | null>(null)

// per-row draft fields
const draftAnchor = ref<Record<number, string>>({})
const draftTol = ref<Record<number, string>>({})

onMounted(load)

async function load() {
  rows.value = await api('/vendors')
  for (const r of rows.value) {
    draftAnchor.value[r.id] = r.anchor_m == null ? '' : String(r.anchor_m)
    draftTol.value[r.id] = r.tolerance_m == null ? '' : String(r.tolerance_m)
  }
}

function flashSaved(id: number) {
  savedId.value = id
  if (savedTimer.value) window.clearTimeout(savedTimer.value)
  savedTimer.value = window.setTimeout(() => (savedId.value = null), 1600)
}

async function save(r: any) {
  const aText = (draftAnchor.value[r.id] ?? '').trim()
  const tText = (draftTol.value[r.id] ?? '').trim()
  const body: Record<string, number | null> = {}
  if (aText === '') {
    body.anchor_m = null
  } else {
    const a = Number(aText)
    if (!Number.isFinite(a) || a < 0) { alert('锚点米标需为不小于 0 的数字'); return }
    body.anchor_m = a
    const t = tText === '' ? 0 : Number(tText)
    if (!Number.isFinite(t) || t < 0) { alert('容差需为不小于 0 的数字'); return }
    body.tolerance_m = t
  }
  const updated = await api('/vendors/' + r.id, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
  const idx = rows.value.findIndex(x => x.id === r.id)
  if (idx >= 0) rows.value[idx] = updated
  draftAnchor.value[r.id] = updated.anchor_m == null ? '' : String(updated.anchor_m)
  draftTol.value[r.id] = updated.tolerance_m == null ? '' : String(updated.tolerance_m)
  flashSaved(r.id)
}

function anchorText(r: any) {
  return r.anchor_m == null ? '无' : `${r.anchor_m} ± ${r.tolerance_m ?? 0} m`
}
</script>
<template>
  <h1>摊主队列</h1>
  <p class="sub">底部排队条 · 宽度与优先级 · 可登记期望锚点米标与容差</p>
  <div class="ss-vendor-queue" style="border-top:none; background:transparent; margin:0; padding:0.5rem 0 1rem">
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="ss-vendor-chip">
      <strong>{{ r.name }}</strong>
      <span>需 {{ r.stall_width_m }} m · 优先 {{ r.priority }}</span>
      <span :class="{ 'ss-chip-anchor': r.anchor_m != null }">锚点：{{ anchorText(r) }}</span>
    </div>
  </div>
  <div class="card">
    <table>
      <thead>
        <tr><th>摊主</th><th>宽度(m)</th><th>优先级</th><th>期望锚点(m)</th><th>容差±(m)</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.name }}</td>
          <td>{{ r.stall_width_m }}</td>
          <td>{{ r.priority }}</td>
          <td>
            <input v-model="draftAnchor[r.id]" inputmode="decimal" placeholder="无锚点" />
          </td>
          <td>
            <input v-model="draftTol[r.id]" inputmode="decimal" placeholder="0" />
          </td>
          <td>
            <div class="ss-anchor-row">
              <button class="btn" @click="save(r)">保存</button>
              <span v-if="savedId === r.id" class="ss-saved">已保存</span>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="muted" style="margin-bottom:0;font-size:0.78rem">
      有锚点的摊位按优先序填空时，起点必须落在「锚点 ± 容差」内；空档够宽但起点越带会被跳过，
      全部不满足则进放不下并记「锚点不符」。锚点留空即按从左填法。
    </p>
  </div>
</template>

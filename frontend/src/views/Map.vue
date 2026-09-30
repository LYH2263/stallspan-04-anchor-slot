<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'
const data = ref<any>(null)
const vendors = ref<any[]>([])

async function run() { data.value = await api('/allocate/run?segment_id=1', { method: 'POST' }) }
onMounted(async () => {
  vendors.value = await api('/vendors')
  await run()
})

const colors = ['#e8a87c','#85dcb8','#e27d60','#c38d9e','#41b3a3','#f4a261','#e76f51']

function pct(m: number) {
  const width = data.value?.segment?.width_m || 1
  return Math.min(100, Math.max(0, (m / width) * 100))
}

const pillars = computed(() => (data.value?.pillars || []).map((p: any) => ({
  left: pct(p.position_m - p.thickness_m / 2),
  width: Math.max((p.thickness_m / (data.value.segment.width_m || 1)) * 100, 0.8),
  label: p.label || '挡柱',
})))

const stalls = computed(() =>
  (data.value?.placements || []).map((p: any, i: number) => ({
    left: pct(p.start_m),
    width: pct(p.end_m) - pct(p.start_m),
    label: p.vendor_name,
    color: colors[i % colors.length],
  })))

// Anchor tolerance bands are drawn for every anchored vendor, placed or not.
// A rejected vendor has no stall block — only the empty band — so an out-of-band
// block can never appear on the map.
const bands = computed(() =>
  vendors.value
    .filter(v => v.anchor_m != null && v.tolerance_m != null)
    .map(v => ({
      key: 'b' + v.id,
      left: pct(v.anchor_m - v.tolerance_m),
      width: pct(v.anchor_m + v.tolerance_m) - pct(v.anchor_m - v.tolerance_m),
      name: v.name,
    })))

// marker ticks: anchor point for anchored vendors
const ticks = computed(() =>
  vendors.value.filter(v => v.anchor_m != null).map(v => ({
    key: 't' + v.id, left: pct(v.anchor_m), name: v.name,
  })))

const rulerTicks = computed(() => {
  const width = data.value?.segment?.width_m || 0
  const step = width > 20 ? 5 : 2
  const arr: any[] = []
  for (let m = 0; m <= width + 1e-9; m += step) arr.push({ m: Math.round(m * 10) / 10, left: pct(m) })
  return arr
})

function chipAnchor(v: any) {
  return v.anchor_m != null ? `锚 ${v.anchor_m}±${v.tolerance_m ?? 0} m` : ''
}
</script>
<template>
  <div class="ss-street-wrap">
    <h1>街段分配带</h1>
    <p class="sub">沿街一维开间 · 挡柱为竖直阻断 · 虚框为期望锚点容差带 · 底部为摊主排队</p>
    <button class="btn" @click="run">重新分配</button>
    <div class="ss-band-ruler" v-if="data">
      <span>0 m</span>
      <span>{{ data.segment.name }} · {{ data.segment.width_m }} m</span>
      <span>{{ data.segment.width_m }} m</span>
    </div>
    <div class="ss-street-band" v-if="data">
      <div class="ss-street-absolute">
        <!-- anchor tolerance bands first (behind stalls) -->
        <div
          v-for="b in bands" :key="b.key" class="ss-anchor-band"
          :style="{ left: b.left + '%', width: b.width + '%' }"
          :title="b.name + ' 锚点容差带'"
        ></div>
        <!-- anchor tick marks -->
        <div
          v-for="t in ticks" :key="t.key" class="ss-anchor-tick"
          :style="{ left: t.left + '%' }" :title="t.name + ' 期望锚点'"
        ></div>
        <!-- stalls: positioned exactly at the engine-computed start -->
        <div
          v-for="(s,i) in stalls" :key="'s'+i" class="ss-band-cell ss-stall"
          :style="{ left: s.left + '%', width: s.width + '%', background: s.color }"
        >{{ s.label }}</div>
        <!-- pillars on top -->
        <div
          v-for="(p,i) in pillars" :key="'p'+i" class="ss-band-cell ss-pillar ss-pillar-abs"
          :style="{ left: p.left + '%', width: p.width + '%' }"
        >{{ p.label }}</div>
      </div>
      <div class="ss-meter-ticks">
        <span v-for="t in rulerTicks" :key="t.m" :style="{ left: t.left + '%' }">{{ t.m }}</span>
      </div>
    </div>
    <div class="ss-legend">
      <span><i class="lg-band"></i>锚点容差带</span>
      <span><i class="lg-tick"></i>期望锚点</span>
      <span><i class="lg-pillar"></i>挡柱</span>
    </div>
    <div class="ss-vendor-queue">
      <div v-for="v in vendors" :key="v.id" class="ss-vendor-chip">
        <strong>{{ v.name }}</strong>
        <span>需 {{ v.stall_width_m }} m · 优先 {{ v.priority }}</span>
        <span v-if="chipAnchor(v)" class="ss-chip-anchor">{{ chipAnchor(v) }}</span>
      </div>
    </div>
    <div class="card" v-if="data">
      <table>
        <thead><tr><th>摊主</th><th>起点</th><th>终点</th><th>宽度</th><th>锚点/容差</th></tr></thead>
        <tbody>
          <tr v-for="p in data.placements" :key="p.vendor_id">
            <td>{{ p.vendor_name }}</td><td>{{ p.start_m }}</td><td>{{ p.end_m }}</td><td>{{ p.width_m }}</td>
            <td>{{ p.anchor_m != null ? p.anchor_m + ' ± ' + p.tolerance_m : '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

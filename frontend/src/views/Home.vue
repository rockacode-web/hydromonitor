<template>
  <VContainer class="fill-height">
    <VResponsive class="align-center text-center fill-height">
      <VImg height="350" class="mb-5" src="@/assets/logo.svg" />

      <div class="text-body-2 font-weight-light mb-n1">Welcome to</div>
      <h1 class="text-h2 font-weight-bold">Elet2415</h1>
      <div class="text-body-1 font-weight-light mt-1">Practices in Electronics II</div>

      <div class="py-10">
        <VRow justify="center">
          <VCol cols="12" md="10" lg="8">
            <VCard variant="tonal" color="surface" class="pa-4 text-left">
              <VCardTitle class="d-flex align-center justify-space-between">
                <div>
                  <div class="text-h6 font-weight-bold">Live Sensor</div>
                  <div class="text-caption">
                    API:
                    <b :class="apiOk ? 'text-success' : 'text-error'">
                      {{ apiOk ? "Connected" : "Disconnected" }}
                    </b>
                    <span class="ml-2">Endpoint: <b>/api/climo/latest</b></span>
                  </div>
                </div>

                <VChip :color="apiOk ? 'success' : 'error'" variant="flat" label>
                  {{ apiOk ? "OK" : "DOWN" }}
                </VChip>
              </VCardTitle>

              <VCardText>
                <VAlert
                  v-if="lastError"
                  type="error"
                  variant="tonal"
                  class="mb-4"
                  title="API Error"
                >
                  {{ lastError }}
                </VAlert>

                <VRow>
                  <VCol cols="12" md="4">
                    <VSheet class="pa-4 rounded-lg" color="surface" border>
                      <div class="text-caption">Temperature (°C)</div>
                      <div class="text-h4 font-weight-bold">{{ fmt(sensor.temperature) }}</div>
                    </VSheet>
                  </VCol>

                  <VCol cols="12" md="4">
                    <VSheet class="pa-4 rounded-lg" color="surface" border>
                      <div class="text-caption">Humidity (%)</div>
                      <div class="text-h4 font-weight-bold">{{ fmt(sensor.humidity) }}</div>
                    </VSheet>
                  </VCol>

                  <VCol cols="12" md="4">
                    <VSheet class="pa-4 rounded-lg" color="surface" border>
                      <div class="text-caption">Heat Index (°C)</div>
                      <div class="text-h4 font-weight-bold">{{ fmt(sensor.heatindex) }}</div>
                    </VSheet>
                  </VCol>
                </VRow>

                <div class="text-caption mt-4">Last update</div>
                <div class="text-body-1">
                  {{ sensor.timestamp ? new Date(sensor.timestamp * 1000).toLocaleString() : "—" }}
                </div>
              </VCardText>
            </VCard>
          </VCol>
        </VRow>
      </div>
    </VResponsive>
  </VContainer>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from "vue";

const sensor = ref({ temperature: null, humidity: null, heatindex: null, timestamp: null });
const apiOk = ref(false);
const lastError = ref("");

let timer = null;

function fmt(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n.toFixed(1);
}

async function fetchLatest() {
  try {
    const res = await fetch("/api/climo/latest");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const out = await res.json();

    if (out && out.status === "success" && out.data) {
      sensor.value = out.data;
      apiOk.value = true;
      lastError.value = "";
    } else {
      apiOk.value = false;
      lastError.value = "Bad response format from API.";
    }
  } catch (e) {
    apiOk.value = false;
    lastError.value = String(e?.message || e);
  }
}

onMounted(() => {
  fetchLatest();
  timer = setInterval(fetchLatest, 2000);
});

onBeforeUnmount(() => {
  if (timer) clearInterval(timer);
});
</script>

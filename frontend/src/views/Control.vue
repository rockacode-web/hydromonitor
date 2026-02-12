<template>
  <VContainer class="d-flex align-center justify-center" fluid>
    <VRow class="d-flex align-center justify-center" style="max-width: 1200px;">
      <VCol class="d-flex flex-column align-center justify-center" cols="12" md="6">
        <VSheet class="mb-1 rounded-t-lg" color="surface" :elevation="0" max-width="800" width="100%">
          <VCard
            class="text-secondary"
            title="LED Controls"
            subtitle="Adjust settings → sent to backend → MQTT"
            variant="tonal"
            flat
            color="surface"
          />
        </VSheet>

        <VSheet class="mb-2" color="surface" :elevation="0" max-width="800" width="100%">
          <VAlert v-if="statusMsg" :type="statusType" variant="tonal" class="ma-2">
            <div><b>{{ statusTitle }}</b></div>
            <div class="text-caption">Endpoint: <b>/api/mqtt/control</b></div>
            <div class="text-caption">Last: {{ lastSent }}</div>
          </VAlert>
        </VSheet>

        <VSheet class="mb-1" color="surface" :elevation="0" max-width="800" width="100%">
          <VCard class="pt-5" variant="tonal" color="surface">
            <VSlider
              class="pt-2 bg-surface"
              append-icon="mdi:mdi-car-light-high"
              density="compact"
              thumb-size="16"
              color="secondary"
              label="Brightness"
              direction="horizontal"
              min="0"
              max="250"
              step="10"
              show-ticks
              thumb-label="always"
              v-model="led.brightness"
            />
          </VCard>
        </VSheet>

        <VSheet class="mb-1" color="surface" :elevation="0" max-width="800" width="100%">
          <VCard class="pt-5 d-flex justify-center align-center" variant="tonal" color="surface">
            <VSlider
              class="pt-2 bg-surface"
              append-icon="mdi:mdi-led-on"
              density="compact"
              thumb-size="16"
              color="secondary"
              label="LED Nodes"
              direction="horizontal"
              min="1"
              max="7"
              step="1"
              show-ticks
              thumb-label="always"
              v-model="led.leds"
            />
          </VCard>
        </VSheet>

        <VSheet class="mb-1 pa-2 border d-flex justify-center align-center" color="surface" :elevation="0" max-width="800" width="100%">
          <VProgressCircular
            rotate="0"
            size="200"
            width="15"
            :model-value="led.leds * 15"
            :color="indicatorColor"
          >
            <span class="text-onSurface font-weight-bold">{{ led.leds }} LED(s)</span>
          </VProgressCircular>
        </VSheet>
      </VCol>

      <VCol class="d-flex align-center justify-center" cols="12" md="6">
        <VColorPicker v-model="led.color" show-swatches mode="rgba" />
      </VCol>
    </VRow>
  </VContainer>
</template>

<script setup>
import { reactive, computed, watch, ref } from "vue";

const led = reactive({
  type: "controls",
  brightness: 255,
  leds: 7,
  color: { r: 255, g: 255, b: 255, a: 1 }
});

const indicatorColor = computed(
  () => `rgba(${led.color.r},${led.color.g},${led.color.b},${led.color.a})`
);

const statusMsg = ref("");
const statusType = ref("info");
const statusTitle = ref("Status");
const lastSent = ref("—");

let timer = null;
const DEBOUNCE_MS = 400;

async function sendControls() {
  const payload = {
    type: "controls",
    brightness: led.brightness,
    leds: led.leds,
    color: led.color
  };

  lastSent.value = JSON.stringify(payload);

  try {
    const res = await fetch("/api/mqtt/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      statusType.value = "error";
      statusTitle.value = `API Error (HTTP ${res.status})`;
      statusMsg.value = "Backend endpoint not reachable (check Vite proxy + Flask running).";
      return;
    }

    const out = await res.json();
    if (out.status === "success") {
      statusType.value = "success";
      statusTitle.value = "Sent ✅";
      statusMsg.value = `Published to MQTT topic: ${out.topic}`;
    } else {
      statusType.value = "error";
      statusTitle.value = "Backend Error";
      statusMsg.value = out.message || "Unknown backend error";
    }
  } catch (e) {
    statusType.value = "error";
    statusTitle.value = "Network Error";
    statusMsg.value = String(e?.message || e);
  }
}

watch(
  led,
  () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(sendControls, DEBOUNCE_MS);
  },
  { deep: true }
);
</script>

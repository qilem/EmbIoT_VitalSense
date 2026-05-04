#include "vitals_state.h"
#include <string.h>
#include <math.h>

/* -----------------------------------------------------------------------
 * Thresholds (all times in milliseconds unless noted)
 * ----------------------------------------------------------------------- */
#define NO_SIGNAL_ENERGY    0.05f   /* signal < this → no_signal */
#define NO_SIGNAL_HOLD_MS   2000    /* must be low for 2 s */
#define CRITICAL_HOLD_MS    10000   /* no_signal for 10 s → critical */
#define STRESS_BPM_DELTA    20.f    /* BPM above baseline → stress */
#define STRESS_HOLD_MS      30000   /* must be elevated for 30 s */
#define BASELINE_ALPHA      0.001f  /* EMA decay ≈ 5-min time constant at 1 Hz */
#define WARMUP_MS           5000    /* first 5 s stay in CALIBRATING */

/* -----------------------------------------------------------------------
 * State
 * ----------------------------------------------------------------------- */
static VitaStatus s_status;
static float      s_bpm_baseline;
static uint32_t   s_no_signal_since_ms;
static uint32_t   s_stress_since_ms;
static bool       s_baseline_seeded;

void vitals_state_init(void)
{
    memset(&s_status, 0, sizeof(s_status));
    s_status.state = VITA_STATE_CALIBRATING;
    s_bpm_baseline = 72.f;
    s_no_signal_since_ms = 0;
    s_stress_since_ms    = 0;
    s_baseline_seeded    = false;
}

void vitals_state_update(const VitalsResult *dsp, uint32_t now_ms)
{
    /* Copy raw DSP fields */
    s_status.bpm        = dsp->bpm;
    s_status.rr         = dsp->rr;
    s_status.signal     = dsp->signal;
    s_status.target_bin = dsp->target_bin;
    s_status.present    = dsp->present;
    s_status.timestamp_s = now_ms / 1000;

    /* Warmup: stay calibrating until we have enough history */
    if (now_ms < WARMUP_MS) {
        s_status.state = VITA_STATE_CALIBRATING;
        return;
    }

    /* No-signal tracking */
    if (dsp->signal < NO_SIGNAL_ENERGY) {
        if (s_no_signal_since_ms == 0) s_no_signal_since_ms = now_ms;
    } else {
        s_no_signal_since_ms = 0;
    }

    /* BPM baseline EMA — only update when we have a valid reading */
    if (dsp->present && dsp->bpm > 30.f && dsp->bpm < 200.f) {
        if (!s_baseline_seeded) {
            s_bpm_baseline  = dsp->bpm;
            s_baseline_seeded = true;
        } else {
            s_bpm_baseline = s_bpm_baseline * (1.f - BASELINE_ALPHA)
                           + dsp->bpm * BASELINE_ALPHA;
        }
    }

    /* Stress tracking */
    bool is_elevated = (dsp->present && dsp->bpm > s_bpm_baseline + STRESS_BPM_DELTA);
    if (is_elevated) {
        if (s_stress_since_ms == 0) s_stress_since_ms = now_ms;
    } else {
        s_stress_since_ms = 0;
    }

    /* State machine (priority: critical > no_signal > stress > normal) */
    if (s_no_signal_since_ms > 0 &&
        (now_ms - s_no_signal_since_ms) >= CRITICAL_HOLD_MS) {
        s_status.state = VITA_STATE_CRITICAL;
    } else if (s_no_signal_since_ms > 0 &&
               (now_ms - s_no_signal_since_ms) >= NO_SIGNAL_HOLD_MS) {
        s_status.state = VITA_STATE_NO_SIGNAL;
    } else if (s_stress_since_ms > 0 &&
               (now_ms - s_stress_since_ms) >= STRESS_HOLD_MS) {
        s_status.state = VITA_STATE_STRESS;
    } else {
        s_status.state = VITA_STATE_NORMAL;
    }
}

VitaStatus vitals_state_get(void) { return s_status; }

const char *vitals_state_name(VitaState s)
{
    switch (s) {
        case VITA_STATE_CALIBRATING: return "calibrating";
        case VITA_STATE_NORMAL:      return "normal";
        case VITA_STATE_STRESS:      return "stress";
        case VITA_STATE_CRITICAL:    return "critical";
        case VITA_STATE_NO_SIGNAL:   return "no_signal";
        default:                     return "unknown";
    }
}

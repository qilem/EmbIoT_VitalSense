#pragma once
#include <stdint.h>
#include <stdbool.h>

/* -----------------------------------------------------------------------
 * Radar DSP constants — must match firmware radar configuration.
 * ----------------------------------------------------------------------- */
#define VITALS_SAMPLE_PER_CHIRP   128
#define VITALS_WINDOW_CHIRPS      512          /* 2.56 s @ 200 Hz — ring=256KB, safe for CM4 1MB SRAM */
#define VITALS_STRIDE             64
#define VITALS_BIN_OFFSET         5            /* skip first 5 range bins */
#define VITALS_PRT_S              0.005f       /* 5 ms PRT → 200 Hz slow-time */
#define VITALS_F_CENTER_HZ        60.5e9f
#define VITALS_IF_SCALE           (16.0f * 3.3f)  /* from pipeline.py */

/* -----------------------------------------------------------------------
 * Output populated by vitals_dsp_process() once per VITALS_STRIDE chirps.
 * ----------------------------------------------------------------------- */
typedef struct {
    float    bpm;           /* heart rate estimate, beats per minute */
    float    rr;            /* respiratory rate, breaths per minute   */
    float    signal;        /* normalized target-bin energy [0,1]     */
    int      target_bin;    /* selected range bin index               */
    bool     present;       /* true if energy exceeds detection floor */
} VitalsResult;

/* -----------------------------------------------------------------------
 * Public API
 * ----------------------------------------------------------------------- */
void vitals_dsp_init(void);

/* Push one chirp (VITALS_SAMPLE_PER_CHIRP uint16 ADC samples).
 * Returns true when a fresh VitalsResult is ready (every VITALS_STRIDE chirps). */
bool vitals_dsp_push(const uint16_t *samples, VitalsResult *out);

#pragma once
#include "vitals_dsp.h"

typedef enum {
    VITA_STATE_CALIBRATING = 0,
    VITA_STATE_NORMAL,
    VITA_STATE_STRESS,
    VITA_STATE_CRITICAL,
    VITA_STATE_NO_SIGNAL,
} VitaState;

typedef struct {
    VitaState state;
    float     bpm;
    float     rr;
    float     signal;
    int       target_bin;
    bool      present;
    uint32_t  timestamp_s;
} VitaStatus;

void        vitals_state_init(void);
void        vitals_state_update(const VitalsResult *dsp, uint32_t now_ms);
VitaStatus  vitals_state_get(void);
const char *vitals_state_name(VitaState s);

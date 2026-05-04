#pragma once
#include "vitals_state.h"
#include "USB_CDC.h"

/* Emit one JSON line over USB-CDC.
 * Call at ~1 Hz from the main loop. */
void usb_proto_emit(USB_CDC_HANDLE cdc_handle, const VitaStatus *status);

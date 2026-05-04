#include "usb_proto.h"
#include <stdio.h>
#include <string.h>

/* JSON line format (newline-delimited, ≤128 bytes):
 * {"bpm":72,"rr":16,"state":"normal","signal":0.85,"bin":12,"present":true,"ts":172345}
 */

static char s_buf[160];

void usb_proto_emit(USB_CDC_HANDLE cdc_handle, const VitaStatus *status)
{
    int len = snprintf(s_buf, sizeof(s_buf),
        "{\"bpm\":%.0f,\"rr\":%.0f,\"state\":\"%s\","
        "\"signal\":%.2f,\"bin\":%d,\"present\":%s,\"ts\":%lu}\n",
        (double)status->bpm,
        (double)status->rr,
        vitals_state_name(status->state),
        (double)status->signal,
        status->target_bin,
        status->present ? "true" : "false",
        (unsigned long)status->timestamp_s);

    if (len > 0 && len < (int)sizeof(s_buf)) {
        USBD_CDC_Write(cdc_handle, s_buf, (unsigned)len, 0);
        USBD_CDC_WaitForTX(cdc_handle, 0);
    }
}

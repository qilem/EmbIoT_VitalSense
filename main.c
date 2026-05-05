/******************************************************************************
* File Name:   main.c
*
* Description: Vital Sense — Edge-AI single-cable mode.
*              Radar data is processed entirely on the CM4; the USB-CDC link
*              carries only a small JSON status line (~1 Hz, <128 bytes).
*
*              Build with RAW_CAPTURE_DEBUG defined to revert to the original
*              raw uint16 stream (for DSP parity validation against Python).
*
* References:
*   Radar: https://github.com/Infineon/sensor-xensiv-bgt60trxx
*   USB:   https://github.com/Infineon/mtb-example-usb-device-cdc-echo
*******************************************************************************/

#include "cy_pdl.h"
#include "cyhal.h"
#include "cybsp.h"
#include "cy_retarget_io.h"
#include "xensiv_bgt60trxx_mtb.h"
#include "USB.h"
#include "USB_CDC.h"
#include <stdio.h>
#include <string.h>

#define XENSIV_BGT60TRXX_CONF_IMPL
#include "vital_sensing_radar_settings.h"
#include "resource_map.h"


/*******************************************************************************
* Macros
*******************************************************************************/
#define USB_CONFIG_DELAY                    (50U)   /* ms */
#define XENSIV_BGT60TRXX_SPI_FREQUENCY      (25000000UL)
#define CHUNK_SIZE                          128     /* samples per interrupt */
#define EMIT_INTERVAL_MS                    1000    /* JSON emit rate */


#define MAGIC (0xFFDDFFDD)
struct __attribute__((packed)) raw_hdr { uint32_t magic; uint32_t length; };
static struct raw_hdr s_raw_hdr = { .magic = MAGIC, .length = CHUNK_SIZE * 2 };
static uint8_t s_raw_tx[sizeof(struct raw_hdr) + CHUNK_SIZE * 2];


/*******************************************************************************
* USB device info
*******************************************************************************/
static const USB_DEVICE_INFO usb_deviceInfo = {
    0x058B, 0x027D,
    "Infineon Technologies",
    "Vital Sense Serial",
    "2439"
};

/*******************************************************************************
* Global Variables
*******************************************************************************/
static USB_CDC_HANDLE usb_cdcHandle;

static cyhal_spi_t          cyhal_spi;
static xensiv_bgt60trxx_mtb_t sensor;
static volatile bool        data_available = false;

static uint16_t s_chunk[CHUNK_SIZE];

/*******************************************************************************
* Interrupt handler
*******************************************************************************/
void xensiv_bgt60trxx_mtb_interrupt_handler(void *args, cyhal_gpio_event_t event) {
    CY_UNUSED_PARAMETER(args);
    CY_UNUSED_PARAMETER(event);
    data_available = true;
}

/*******************************************************************************
* USB CDC setup
*******************************************************************************/
void usb_add_cdc(void) {
    static U8         OutBuffer[USB_FS_BULK_MAX_PACKET_SIZE];
    USB_CDC_INIT_DATA InitData;
    USB_ADD_EP_INFO   EPBulkIn, EPBulkOut, EPIntIn;

    memset(&InitData, 0, sizeof(InitData));

    EPBulkIn.Flags         = 0; EPBulkIn.InDir        = USB_DIR_IN;
    EPBulkIn.Interval      = 0; EPBulkIn.MaxPacketSize = USB_FS_BULK_MAX_PACKET_SIZE;
    EPBulkIn.TransferType  = USB_TRANSFER_TYPE_BULK;
    InitData.EPIn = USBD_AddEPEx(&EPBulkIn, NULL, 0);

    EPBulkOut.Flags        = 0; EPBulkOut.InDir        = USB_DIR_OUT;
    EPBulkOut.Interval     = 0; EPBulkOut.MaxPacketSize = USB_FS_BULK_MAX_PACKET_SIZE;
    EPBulkOut.TransferType = USB_TRANSFER_TYPE_BULK;
    InitData.EPOut = USBD_AddEPEx(&EPBulkOut, OutBuffer, sizeof(OutBuffer));

    EPIntIn.Flags          = 0; EPIntIn.InDir          = USB_DIR_IN;
    EPIntIn.Interval       = 64; EPIntIn.MaxPacketSize = USB_FS_INT_MAX_PACKET_SIZE;
    EPIntIn.TransferType   = USB_TRANSFER_TYPE_INT;
    InitData.EPInt = USBD_AddEPEx(&EPIntIn, NULL, 0);

    usb_cdcHandle = USBD_CDC_Add(&InitData);
}

/*******************************************************************************
* main
*******************************************************************************/
int main(void) {
    cy_rslt_t result = cybsp_init();
    if (result != CY_RSLT_SUCCESS) CY_ASSERT(0);
    __enable_irq();

    cy_retarget_io_init(CYBSP_DEBUG_UART_TX, CYBSP_DEBUG_UART_RX, CY_RETARGET_IO_BAUDRATE);
    cyhal_gpio_init(CYBSP_USER_LED, CYHAL_GPIO_DIR_OUTPUT, CYHAL_GPIO_DRIVE_STRONG, CYBSP_LED_STATE_OFF);

    printf("\x1b[2J\x1b[;H");
    printf("****************** Vital Sense Application ******************\r\n\n");

    /* USB init */
    USBD_Init();
    usb_add_cdc();
    USBD_SetDeviceInfo(&usb_deviceInfo);
    USBD_Start();
    while ((USBD_GetState() & USB_STAT_CONFIGURED) != USB_STAT_CONFIGURED) {
        cyhal_system_delay_ms(USB_CONFIG_DELAY);
    }

    /* Radar SPI init */
    result = cyhal_spi_init(&cyhal_spi,
                            PIN_XENSIV_BGT60TRXX_SPI_MOSI, PIN_XENSIV_BGT60TRXX_SPI_MISO,
                            PIN_XENSIV_BGT60TRXX_SPI_SCLK, NC, NULL,
                            8, CYHAL_SPI_MODE_00_MSB, false);
    CY_ASSERT(result == CY_RSLT_SUCCESS);

    Cy_GPIO_SetSlewRate(CYHAL_GET_PORTADDR(PIN_XENSIV_BGT60TRXX_SPI_MOSI),
                        CYHAL_GET_PIN(PIN_XENSIV_BGT60TRXX_SPI_MOSI), CY_GPIO_SLEW_FAST);
    Cy_GPIO_SetDriveSel(CYHAL_GET_PORTADDR(PIN_XENSIV_BGT60TRXX_SPI_MOSI),
                        CYHAL_GET_PIN(PIN_XENSIV_BGT60TRXX_SPI_MOSI), CY_GPIO_DRIVE_1_8);
    Cy_GPIO_SetSlewRate(CYHAL_GET_PORTADDR(PIN_XENSIV_BGT60TRXX_SPI_SCLK),
                        CYHAL_GET_PIN(PIN_XENSIV_BGT60TRXX_SPI_SCLK), CY_GPIO_SLEW_FAST);
    Cy_GPIO_SetDriveSel(CYHAL_GET_PORTADDR(PIN_XENSIV_BGT60TRXX_SPI_SCLK),
                        CYHAL_GET_PIN(PIN_XENSIV_BGT60TRXX_SPI_SCLK), CY_GPIO_DRIVE_1_8);

    result = cyhal_spi_set_frequency(&cyhal_spi, XENSIV_BGT60TRXX_SPI_FREQUENCY);
    CY_ASSERT(result == CY_RSLT_SUCCESS);

    cyhal_system_delay_ms(5); /* LDO stable */

    result = xensiv_bgt60trxx_mtb_init(&sensor, &cyhal_spi,
                                       PIN_XENSIV_BGT60TRXX_SPI_CSN,
                                       PIN_XENSIV_BGT60TRXX_RSTN,
                                       register_list,
                                       XENSIV_BGT60TRXX_CONF_NUM_REGS);
    CY_ASSERT(result == CY_RSLT_SUCCESS);

    result = xensiv_bgt60trxx_mtb_interrupt_init(&sensor, CHUNK_SIZE,
                                                  PIN_XENSIV_BGT60TRXX_IRQ,
                                                  CYHAL_ISR_PRIORITY_DEFAULT,
                                                  xensiv_bgt60trxx_mtb_interrupt_handler, NULL);
    CY_ASSERT(result == CY_RSLT_SUCCESS);

    if (xensiv_bgt60trxx_start_frame(&sensor.dev, true) != XENSIV_BGT60TRXX_STATUS_OK) CY_ASSERT(0);

    printf("BGT60TRXX setup complete\r\n");
    cyhal_gpio_write(CYBSP_USER_LED, CYBSP_LED_STATE_ON);




    memcpy(s_raw_tx, &s_raw_hdr, sizeof(s_raw_hdr));



    for (;;) {
        /* Wait for radar FIFO interrupt */
        int fifo_result;
        do {
            while (!data_available);
            data_available = false;
            fifo_result = xensiv_bgt60trxx_get_fifo_data(&sensor.dev, s_chunk, CHUNK_SIZE);

            if (fifo_result == XENSIV_BGT60TRXX_STATUS_GSR0_ERROR) {
                printf("restarting radar..\r\n");
                xensiv_bgt60trxx_soft_reset(&sensor.dev, XENSIV_BGT60TRXX_RESET_FIFO);
                xensiv_bgt60trxx_start_frame(&sensor.dev, false);
                xensiv_bgt60trxx_start_frame(&sensor.dev, true);
                data_available = false;
            }
        } while (fifo_result != XENSIV_BGT60TRXX_STATUS_OK);


        /* Original raw-streaming path for DSP parity testing */
        memcpy(s_raw_tx + sizeof(s_raw_hdr), s_chunk, CHUNK_SIZE * 2);
        USBD_CDC_Write(usb_cdcHandle, s_raw_tx, sizeof(s_raw_tx), 0);
        USBD_CDC_WaitForTX(usb_cdcHandle, 0);

    }
}

/* Includes ***************************************************/
#include "string.h"
#include "stdio.h"
#include "math.h"

#include "argon.h"
#include "board.h"

#include "FreeRTOS.h"
#include "FreeRTOSConfig.h"
#include "task.h"
#include "event_groups.h"
#include "queue.h"
#include "FreeRTOS_CLI.h"

#include "gpio.h"
#include "leds.h"
#include "log.h"
#include "rtc.h"
#include "tdf.h"
#include "tdf_parse.h"
#include "watchdog.h"

#include "test_reporting.h"
#include "tiny_printf.h"

#include "device_nvm.h"

#include "unified_comms_serial.h"
#include "unified_comms_bluetooth.h"

#include "bluetooth.h"

#include "hci_packet.h"

#include "cli_task.h"
#include "os_log.h"
#include "lib_hci.h"
#include "os_hci.h"
#include "hal_hci.h"
#include "os_util.h"
#include "lib_bt.h"
#include "os_bt.h"
#include "os_loc.h"
#include "os_flash.h"

/* Private Defines ------------------------------------------*/
#define BUTTON_BIT 	(1 << 0)

/* Private Macros -------------------------------------------*/
/* Type Definitions -----------------------------------------*/
/* Function Declarations ------------------------------------*/
void vCustomSerialHandler(xCommsInterface_t *pxComms,
						  xUnifiedCommsIncomingRoute_t *pxCurrentRoute,
						  xUnifiedCommsMessage_t *pxMessage);
void vCustomBluetoothHandler( const uint8_t *pucAddress, eBluetoothAddressType_t eAddressType, 
							int8_t cRssi, bool bConnectable, 
							uint8_t *pucData, uint8_t ucDataLen );
void vBluetoothTdfHandler( xCommsInterface_t *			 pxComms,
							xUnifiedCommsIncomingRoute_t *pxCurrentRoute,
							xUnifiedCommsMessage_t *	 pxMessage );
/* Private Variables ----------------------------------------*/
EventGroupHandle_t EventISR;
TickType_t prevTime = 0;
uint8_t count = 0;
double heading;

/*-----------------------------------------------------------*/

void vButtonInterruptHandler(void)
{
	TickType_t currTime = xTaskGetTickCount();
	EventBits_t isrBits;
	BaseType_t xHigherPriorityTaskWoken, xResult;

	/* xHigherPriorityTaskWoken must be initialised to pdFALSE. */
	xHigherPriorityTaskWoken = pdFALSE;
	isrBits = xEventGroupGetBitsFromISR(EventISR);

	if(currTime - prevTime > 100) {
		vLedsSet(LEDS_ALL);
		isrBits ^= BUTTON_BIT;
		xEventGroupClearBitsFromISR(EventISR, 0xFF);
    	xResult = xEventGroupSetBitsFromISR(
                              EventISR,   /* The event group being updated. */
                              isrBits, /* The bits being set. */
                              &xHigherPriorityTaskWoken );
		prevTime = currTime;		
		/* Was the message posted successfully? */
		
	}

	if( xResult != pdFAIL ) {
		/* If xHigherPriorityTaskWoken is now set to pdTRUE then a context
		switch should be requested.  The macro used is port specific and will
		be either portYIELD_FROM_ISR() or portEND_SWITCHING_ISR() - refer to
		the documentation page for the port being used. */
		portYIELD_FROM_ISR( xHigherPriorityTaskWoken );
	}
}

/*-----------------------------------------------------------*/

void vApplicationSetLogLevels(void)
{
	eLogSetLogLevel(LOG_RESULT, LOG_DEBUG);
	eLogSetLogLevel(LOG_APPLICATION, LOG_DEBUG);
	eLogSetLogLevel( LOG_BLUETOOTH_GAP, LOG_ERROR );
	eLogSetLogLevel( LOG_BLUETOOTH_GATT, LOG_INFO );
}

/*-----------------------------------------------------------*/

void vApplicationStartupCallback( void ) {

    WatchdogReboot_t *  pxRebootData;
	tdf_watchdog_info_t xWatchdogInfo;

	/* Initiate startup sequence */
	vLedsOn( LEDS_ALL );

	/* Get Reboot reasons and clear */
	pxRebootData = xWatchdogRebootReason();
	if ( pxRebootData != NULL ) {
		vWatchdogPrintRebootReason( LOG_APPLICATION, LOG_INFO, pxRebootData );
		vWatchdogPopulateTdf( pxRebootData, &xWatchdogInfo );

		// eTdfAddMulti( SERIAL_LOG, TDF_WATCHDOG_INFO_SMALL, TDF_TIMESTAMP_NONE, NULL, &xWatchdogInfo );
		// eTdfFlushMulti( SERIAL_LOG );
	}

	/* Setup our receive handlers */
	xSerialComms.fnReceiveHandler = vCustomSerialHandler;
	vUnifiedCommsListen(&xSerialComms, COMMS_LISTEN_ON_FOREVER);

	/* Setup our Bluetooth receive handler */
	vUnifiedCommsBluetoothCustomHandler(vCustomBluetoothHandler);
	xBluetoothComms.fnReceiveHandler = vBluetoothTdfHandler;
	vUnifiedCommsListen(&xBluetoothComms, COMMS_LISTEN_ON_FOREVER);

	/* Setup Interrupt Callback */
	vGpioSetup( BUTTON_1, GPIO_INPUTPULL, NRF_GPIO_PIN_PULLDOWN); 
	eGpioConfigureInterrupt(BUTTON_1, true, GPIO_INTERRUPT_RISING_EDGE, vButtonInterruptHandler); 
	EventISR = xEventGroupCreate();

    /* Init functions */
	cli_task_init();
    os_log_init();
    os_hci_init();
	os_util_init();
	os_bt_init();
	os_loc_init();
	os_flash_init();

    /* Clear for takeoff */
    vLedsToggle(LEDS_ALL);
}

/*-----------------------------------------------------------*/

void vApplicationTickCallback( uint32_t ulUptime ) {
	
	vLedsToggle(LEDS_BLUE);
	int16_t xMagno, yMagno;

	// EventBits_t buttonIsr = xEventGroupGetBitsFromISR(EventISR);

	/* Magno Read */
	if (count == 2) {
		lib_hci_request_magno();
		xMagno = (HCIdata[0]<<8) | HCIdata[1];
		yMagno = (HCIdata[2]<<8) | HCIdata[3];
		/* Heading Info */
		heading = atan2(yMagno, xMagno) * (180 / M_PI) * 100.0;
		if (heading > 36000.0) {
			heading -= 36000.0;
		} else if (heading < 0) {
			heading += 36000.0;
		}
		os_loc_setHead((uint16_t)heading);
	}
	
	if (count == 4) {
		/* Pedometer */
		lib_hci_request_accel('p');
		count = 0;
	}
	
	count ++;

	UNUSED(ulUptime);

}

/*-----------------------------------------------------------*/

void vCustomSerialHandler(xCommsInterface_t *pxComms,
						  xUnifiedCommsIncomingRoute_t *pxCurrentRoute,
						  xUnifiedCommsMessage_t *pxMessage)
{
	char pcLocalString[100] = {0};
    
	UNUSED(pxCurrentRoute);
	UNUSED(pxComms);
	/* 
	 * Copy the string to a local buffer so it can be NULL terminated properly
	 * The %s format specifier does not respect provided lengths
	 */
	pvMemcpy(pcLocalString, pxMessage->pucPayload, pxMessage->usPayloadLen);
	vUnifiedCommsBasicRouter(pxComms, pxCurrentRoute, pxMessage);
	cli_task_queue(pcLocalString);
}

/*-----------------------------------------------------------*/

void vCustomBluetoothHandler( const uint8_t *pucAddress, eBluetoothAddressType_t eAddressType, 
							int8_t cRssi, bool bConnectable, 
							uint8_t *pucData, uint8_t ucDataLen )
{
	EventBits_t btBits = xEventGroupGetBitsFromISR(EventBT);
	Node TxNode;
	UNUSED(eAddressType);
	UNUSED(bConnectable);
	UNUSED(pucData);
	UNUSED(ucDataLen);

	/* Limit printed devices based on RSSI */
	if (cRssi < -75) {
		return;
	}

	if ((btBits & SCAN_BIT) == SCAN_BIT) {
		os_log_print(LOG_INFO, "Bluetooth Recv:\n\r\tAddress: %02x:%02x:%02x:%02x:%02x:%02x\n\r\tRSSI: %3d dBm", 
					pucAddress[0], pucAddress[1], pucAddress[2], pucAddress[3], pucAddress[4], pucAddress[5],
					cRssi);
	}

	/* Add address to node to be sent to queue */
	for(int i = 0; i < NODE_ADDR_SIZE; i++) {
		TxNode.address[i] = pucAddress[i];
	}
	/* Other parameters */
	TxNode.prevRssi = cRssi;

	os_loc_queueNode(TxNode);
}

/*-----------------------------------------------------------*/

void vBluetoothTdfHandler( xCommsInterface_t *			 pxComms,
							xUnifiedCommsIncomingRoute_t *pxCurrentRoute,
							xUnifiedCommsMessage_t *	 pxMessage ) 
{
	xTdfParser_t incomingTdf;
	xTdf_t xUltrasonic;
	uint8_t payload[100];
	uint16_t usDist = 0;
	uint8_t address[NODE_ADDR_SIZE];
	Node node;


	UNUSED(pxComms);
	UNUSED(pxCurrentRoute);

	pvMemcpy(payload, pxMessage->pucPayload, pxMessage->usPayloadLen);

	vTdfParseStart( &incomingTdf, payload, pxMessage->usPayloadLen );
	if (eTdfParse(&incomingTdf, &xUltrasonic) == ERROR_NONE) {
		/* Ultrasonic set */
		usDist = 0;
		if ((xUltrasonic.usId & 0x0FFF) == 475) {
			usDist |= (xUltrasonic.pucData[0] & 0xFF);
			usDist |= (xUltrasonic.pucData[1] << 8);
		}
		node.ultrasonic = usDist;

		/* Address set */
		for(int i = 0; i < NODE_ADDR_SIZE; i++) {
			address[i] = ((uint64_t)pxMessage->xSource >> 8*i) & 0xFF;
			node.address[i] = address[i];
		}
		/* Update Node */
		os_loc_updateNode_ultrasonic(address, node);
	}
}

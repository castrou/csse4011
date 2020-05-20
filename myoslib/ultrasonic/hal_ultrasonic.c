/** 
 **************************************************************
 * @file myoslib/ultrasonic/hal_ultrasonic.c
 * @author Cameron Stroud - 44344968
 * @date 18052020
 * @brief Ultrasonic Driver file
 ***************************************************************
 * EXTERNAL FUNCTIONS 
 ***************************************************************
 * 
 *************************************************************** 
 */

/* Includes ***************************************************/
#include "board.h"
#include "tiny_printf.h"

#include "gpio.h"
#include "leds.h"
#include "log.h"

#include "os_log.h"

#include "hal_ultrasonic.h"

/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/
/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/
/* Private function prototypes -----------------------------------------------*/

/*-----------------------------------------------------------*/

/**
* @brief  brief
* @param  None
* @retval None
*/
extern void hal_ultrasonic_init( void ) {

    vGpioSetup( TRIG_PIN, GPIO_PUSHPULL, NRF_GPIO_PIN_SENSE_HIGH); 
    vGpioSetup( ECHO_PIN, GPIO_INPUTPULL, NRF_GPIO_PIN_PULLDOWN); 

}

/*-----------------------------------------------------------*/
/** 
 **************************************************************
 * @file myoslib/ultrasonic/os_ultrasonic.h
 * @author Cameron Stroud - 44344968
 * @date 20052020
 * @brief Ultrasonic OS header file
 ***************************************************************
 * EXTERNAL FUNCTIONS 
 ***************************************************************
 * 
 *************************************************************** 
 */

#ifndef S4434496_OS_US_H
#define S4434496_OS_US_H

/* Global Defines ------------------------------------------------------------*/
#define DISCONNECTED 0x0000
/* Global Variables ----------------------------------------------------------*/
/* Function prototypes -------------------------------------------------------*/
extern void os_ultrasonic_init( void );
extern void os_ultrasonic_deinit( void );
extern double os_ultrasonic_read();

#endif // S4434496_OS_US_H
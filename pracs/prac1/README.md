# Cameron Stroud - 44344968

## CSSE4011 Practical 1

## Design Tasks

### Part A - Build Environment

#### Design Task 1A: EI-FreeRTOS Installation and Integration

EI-FreeRTOS successfully installed and integrated into development environment

#### Design Task 2A: Basic Example

Example program has been made. LEDs cycle through RED > GREEN > BLUE in a repeating pattern.  
Commands from Task 2B will override the current LED state (ie. turning on green during red phase
will show orange, turning off blue during blue phase will show nothing, etc.)

### PART B - Command Line Interface

To use the Command Line Interface, run baselisten on a terminal and submit commands using
send_string "%s", where %s is the desired command input.

#### Design Task 1B: System Timer Control Example

System Timer Control Implemented. Arguments are as follows:  
`'f'`: Format as HH:MM:SS  
**No arguments**: Time in seconds  

Example usage: `time f`

#### Design Task 2B: LED Control Example

LED Control Implemented. Arguments are as follows:  
`'o'`: Turn on  
`'f'`: Turn off  
`'t'`: Toggle  

`'r'`: Red LED  
`'g'`: Green LED  
`'b'`: Blue LED  

Example usage: `led o r`

#### Design Task 3B: Log Message

All messages are coloured depending on their type (ie. LOG\_ERROR, LOG\_INFO, LOG\_DEBUG)

Can be independently viewed or view all using:  
`'e'`: Display only error messages  
`'l'`: Display only generic log messages  
`'d'`: Display only debug messages  
`'a'`: Display all messages  

Example usage: `log a`

**Recommended commands for testing functionality:**  
LOG\_ERROR:  `led f o`  
LOG\_INFO:   `time`  
LOG\_DEBUG:  `led o r`  

### Part C - AHU Base Hardware

#### Design Task: Create a base schematic for the AHU

Base schematic has been created for the AHU in the Grove Shield Feather Wing format (complete with Argon platform symbol).  

---

## Folder Structure

```bash
┌── ei-freertos
├── csse4011-s4434496
|   ├── ei-changes
|   ├── myoslib
|   |   ├── cli
|   |   |   ├── cli_task.c  (+)
|   |   |   └── cli_task.h  (+)
|   |   ├── log
|   |   |   ├── cli_log.c   (+)
|   |   |   ├── cli_log.h   (+)
|   |   |   ├── lib_log.c   (+)
|   |   |   ├── lib_log.h   (+)
|   |   |   ├── os_log.c    (+)
|   |   |   └── os_log.h    (+)
|   |   └── util
|   |       ├── cli_util.c  (+)
|   |       ├── cli_util.h  (+)
|   |       ├── lib_util.c  (+)
|   |       ├── lib_util.h  (+)
|   |       ├── os_util.c   (+)
|   |       └── os_util.h   (+)
|   └── pracs
|       ├── prac1
|       |   ├── inc
|       |   |   ├── application.h       (+)
|       |   |   └── gatt_nrf52.h        (+)
|       |   ├── src
|       |   |   ├── gatt_nrf52.c        (+)
|       |   |   ├── gatt.xml            (+)
|       |   |   └── prac1.c             (+)
|       |   ├── Makefile        (+)  
|       |   └── filelist.mk     (+)  
|       └────── README.md       (+)  
└────── project
```

---

## References

[SnapEDA 2821 Symbol & Footprint](https://www.snapeda.com/parts/2821/Adafruit%20Industries%20LLC/view-part/)  
[FreeRTOS+CLI](https://www.freertos.org/FreeRTOS-Plus/FreeRTOS_Plus_CLI/Download_FreeRTOS_Plus_CLI.html)
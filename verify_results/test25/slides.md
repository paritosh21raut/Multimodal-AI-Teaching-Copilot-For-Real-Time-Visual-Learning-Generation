# test25 — 

Session 20261015-002704-b2ed, 17 slides.

## Slide 01: Operating System
*definition* · Operating System

- **Operating System (OS)**: System software that manages computer hardware and software resources.
- Acts as interface between user, applications, and hardware.
- OS initializes the system when computer turns on
- OS provides environment for applications to run
- OS manages resources required by applications
- For example, when you open a web browser, listen to music or create a document

## Slide 02: Examples and Functions
*key_points* · Operating System

- Microsoft Windows
- Linux
- macOS
- Android
- iOS
- [hierarchy]
  - Key OS Functions
    - Process management
    - Memory management
    - File management
    - Device management
    - Security

## Slide 03: Process Management
*definition* · Operating System

- **Process**: A program that is currently executing
- OS creates processes
- OS schedules processes for execution
- OS manages process states
- Second core function is Memory Management
- [image] Process State Diagram (Public domain)

## Slide 04: Memory Management
*definition* · Operating System

- **Memory Management**: Controls how computer memory (RAM) is allocated to programs
- OS allocates memory when application starts
- OS reclaims memory when application closes
- Isolates processes from each other
- Supports virtual memory
- [image] Virtual memory diagram (CC BY-SA 4.0)

## Slide 05: File Management
*definition* · Operating System

- **File Management**: Organizes information into files and directories
- Provides operations for creating, reading, writing, renaming, deleting files
- Manages file permissions and storage locations

## Slide 06: Device Management
*definition* · Operating System

- **Device Management**: Coordinates hardware devices like keyboards, mics, printers, displays, and storage drives
- Device drivers enable OS communication with hardware

## Slide 07: Security and Protection
*definition* · Operating System

- **Security and Protection**: Protects data and resources using user accounts, permissions, and authentication
- Isolates processes from each other
- Controls program access to resources

## Slide 08: Operating System (part 1)
*definition* · Operating System

- **Batch Operating System**: Processes jobs in batches without continuous user interaction
- Similar jobs grouped and executed sequentially
- Jobs executed according to scheduling policy
- [example] Payroll processing; Large scale data processing

## Slide 09: Operating System (part 2)
*concept* · Operating System

- **Time Sharing Operating System**: Allows multiple users to share computing resources by allocating small CPU time intervals.
- Used by many general purpose operating systems
- Allows different processes or threads to execute in parallel.
- **Multitasking Operating System**: Allows multiple applications to make progress during the same period.
- **Multi-processing Operating System**: Supports computers with two or more processing units or CPU cores.

## Slide 10: Operating System (part 1)
*concept* · Operating System

- **Kernel**: Central part of the operating system managing CPU, memory, and hardware access.
- An operating system contains several important components that work together
- **Shell**: Interface for users to interact with the operating system.

## Slide 11: Operating System (part 2)
*concept* · Operating System

- *Types of User Interfaces*
- Command Line Interface
  - Text-based commands
- Graphical User Interface
  - Windows
  - Icons
  - Menus
  - Visual controls
- **Device Drivers**: Software components enabling OS communication with specific hardware devices
- **File System**: Organizes files and directories and manages data storage and retrieval
- **System Library and Services**: Provides commonly used functions and background services for applications
- **System Calls**: Requests from applications to the OS for services like process creation or file access

## Slide 12: Operating System (part 3)
*definition* · Operating System

- **Kernel**: Core component of the operating system that manages access to essential system resources with elevated privileges
- *Kernel Functions*
- Schedules processes and threads
- Manages memory
- Handles interrupts
- Coordinates hardware access
- Provides system call interface
- Enforces isolation and protection

## Slide 13: Kernel Designs
*concept* · Operating System

- [hierarchy]
  - Kernel Designs
    - Monolithic Kernel
    - Microkernel
- **Monolithic Kernel**: Places many core operating system services in kernel space
- **Microkernel**: Keeps kernel small and moves services into separate processes
- **Hybrid Kernel**: Combines design approaches from different kernel architectures
- [note] Affects performance, modularity, isolation, and complexity

## Slide 14: Process Management (part 1)
*definition* · Operating System

- **Process**: A program in execution
- Contains execution state
- Tracks allocated resources
- Stores scheduling information
- Waiting for an event such as completion of an input-output operation
- [image] Process State Diagram (Public domain)
- [hierarchy]
  - Common Process States
    - New: Process being created
    - Ready: Waiting for CPU time
    - Running: Executing on CPU
    - Waiting: Awaiting I/O completion

## Slide 15: Process Management (part 2)
*key_points* · Operating System

- *Process State*
- Terminated: Execution finished or stopped
- [image] Process State Diagram (Public domain)

## Slide 16: Memory Management (part 1)
*concept* · Operating System

- **Memory Management**: Controls the allocation and use of RAM
- Ensures programs receive suitable memory sources
- Prevents improper interfacing between programs
- **Virtual Memory**: Provides a virtual address space translated to physical addresses
- Allows operation without contiguous physical RAM
- Supports program isolation
- Allows parts of address space on storage

## Slide 17: Memory Management (part 2)
*key_points* · Operating System

- Storage is much slower than RAM
- Frequent page movement reduces performance
- This situation is called thrashing

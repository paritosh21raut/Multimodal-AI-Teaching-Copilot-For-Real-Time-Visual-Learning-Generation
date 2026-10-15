# test26 — 

Session 20261015-003814-8faf, 20 slides.

## Slide 01: What is VLSI?
*definition* · VLSI

- **VLSI**: Very Large Scale Integration; integrating many electronic components onto a single integrated circuit
- Early systems used individual electronic components
- IC technology places multiple components on one chip
- Advancing fabrication technology increases transistor count
- VLSI enables high-performance and energy-efficient electronic systems
- [example] Smartphone processor contains billions of transistors; Transistors execute instructions and process images; Transistors manage memory and perform calculations

## Slide 02: Applications
*key_points* · VLSI

- Microprocessors and microcontrollers
- Smartphones and computers
- Artificial intelligence accelerators
- Digital signal processors
- Memory devices
- Automotive electronics
- Wireless communication systems

## Slide 03: What is Integrated Circuit (IC)?
*definition* · Integrated Circuits

- **Integrated Circuit (IC)**: Electronic circuit fabricated on semiconductor material, usually silicon, containing transistors and resistors.
- ICs include capacitors and interconnections
- Components depend on design and manufacturing
- Circuits are integrated internally, not externally

## Slide 04: Advantages
*key_points* · Integrated Circuits

- Smaller size
- Reduced power consumption
- High reliability
- Economical mass production
- [example] Microcontroller IC contains processor core

## Slide 05: Classification (part 1)
*hierarchy* · Integrated Circuits

- [hierarchy]
  - Types of Integrated Circuits
    - Digital ICs
    - Analog ICs
    - Mixed signal ICs
- [note] Memory, timers, communication interfaces, and other peripherals
- Digital ICs process binary information
- Analog ICs process continuously varying signals
- Mixed signal ICs combine analog and digital circuitry

## Slide 06: Transistors (part 1)
*concept* · VLSI

- **Transistor**: Semiconductor device that controls electrical current
- Building block of VLSI
- Fundamental to modern integrated circuits
- **MOSFET**: Metal Oxide Semiconductor Field Effect transistor
- MOSFET has three primary terminals: gate, source, drain
- Body or substrate terminal is also present
- Gate voltage controls conduction between source and drain

## Slide 07: Transistors (part 2)
*groups* · VLSI

- *MOSFET Types*
- NMOS
  - Uses n-type channel when on
- PMOS
  - Uses p-type channel when on
- nMOS and pMOS combine to build CMOS circuits
- Transistors act as electronic switches
- Enable representation and processing of binary values

## Slide 08: CMOS Technology (part 1)
*concept* · VLSI

- **CMOS**: Complementary Metal Oxide Semiconductor
- Uses complementary NMOS and PMOS transistors
- Implements electronic circuits
- Widely used in modern digital ICs
- Has very low static power consumption
- **CMOS Inverter**: Circuit with PMOS to VDD and NMOS to ground

## Slide 09: CMOS Technology (part 2)
*process_flow* · VLSI

- [process]
  1. Input low: pMOS on, nMOS off, output high
  2. Input high: pMOS off, nMOS on, output low
  3. Circuit performs NOT operation
- [example] Processors; Memory devices; Digital logic; Image sensors

## Slide 10: Digital Logic Design (part 1)
*members* · VLSI

- **Digital circuits**: Operate on discrete logical values 0 and 1
- Digital Logic Design is essential for VLSI engineering
- [hierarchy]
  - Basic Logic Gates
    - AND
    - OR
    - NOT
    - NAND
    - NOR
    - XOR
- [example] AND gate outputs 1 only when both inputs are 1

## Slide 11: Digital Logic Design (part 2)
*formula* · VLSI

- [formula] Y = A \cdot B
  - {'symbol': 'Y', 'meaning': 'Output', 'unit': '', 'latex': 'Y'}
  - {'symbol': 'A, B', 'meaning': 'Inputs', 'unit': '', 'latex': 'A ,\\quad B'}
- **NOT Gate**: Output is A-bar (inverted input)
- NOT gate output is A-bar
- Gates combine to build complex systems
- Examples: adders, multiplexers, counters, registers, processors
- Boolean Algebra and logic gates are prerequisites for advanced VLSI design

## Slide 12: Digital Logic Design (part 3)
*hierarchy* · VLSI

- [hierarchy]
  - Digital Circuits
    - Combinational Circuits
    - Sequential Circuits
- [example] Adders and subtractors; Multiplexers, encoders, decoders; Comparators
- **Half Adder**: Adds two binary input bits to produce a sum and a carry

## Slide 13: Digital Logic Design (part 4)
*formula* · VLSI

- [formula] S = A \text{XOR} B ,\quad C = A \cdot B
  - {'symbol': 'S', 'meaning': 'Sum', 'unit': '', 'latex': 'S'}
  - {'symbol': 'C', 'meaning': 'Carry', 'unit': '', 'latex': 'C'}
- **Sequential Circuits**: Circuits where output depends on current inputs and stored state
- Uses memory elements like latches and flip-flops
- [example] Registers; Counters

## Slide 14: Digital Logic Design (part 5)
*key_points* · VLSI

- Use clock signals to coordinate state changes
- Essential for implementing processors
- Used in control units and digital communication systems
- Verilog counter module with clock, reset, and 4-bit count output
- Verilog uses 'always @(posedge clock or posedge reset)' block
- Reset condition: count <= 4'b0000
- [example] Counter increments value on every active clock edge

## Slide 15: Digital Logic Design (part 6)
*key_points* · VLSI

- Else condition: count increments on rising clock edge
- Module describes 4-bit counter
- Asynchronous active-high reset
- Reset sets counter to zero
- Single inverted comma b1 semicolon end end module
- RTL describes digital hardware before physical conversion

## Slide 16: VLSI Design Flow (part 1)
*definition* · VLSI

- **VLSI Design Flow**: Series of steps transforming design idea into manufacturable integrated circuit
- Engineers define required functionality
- Engineers specify performance requirements
- Engineers set power consumption limits
- Engineers determine operating temperature

## Slide 17: VLSI Design Flow (part 2)
*process_flow* · VLSI

- [process]
  1. Engineers set area constraints
  2. Architecture design: divide system into functional blocks
  3. Engineers decide how functional blocks interact
  4. RTL description: describe digital logic using Verilog or VHDL
  5. Functional verification: simulate to check design behavior
  6. Logic synthesis: translate RTL into logic cell network
  7. Physical design: floor planning, placement, clock tree synthesis, routing, timing analysis
  8. Sign-off: static timing, design rule, layout vs schematic checks
  9. Fabrication: prepare design for semiconductor manufacturing
  10. Testing: evaluate chip functionality and performance
- [note] The precise sequence and terminology vary by design, type and manufacturing processes

## Slide 18: FPGA
*key_points* · FPGA vs ASIC

- FPGA and ASIC implement digital hardware
- Configurable after manufacturing
- Useful for prototyping hardware
- Useful for experimentation
- Useful for configurable logic applications
- **FPGA**: Field Programmable Gate Array
- FPGA contains configurable logic blocks
- FPGA contains programmable interconnections
- FPGA contains other resources

## Slide 19: ASIC (part 1)
*definition* · FPGA vs ASIC

- **ASIC**: Application Specific Integrated Circuit
- Designed for specific applications
- Hardware structure fixed during manufacturing
- Excellent performance and power efficiency
- High area efficiency
- High development and manufacturing costs
- FPGAs used to evaluate algorithms before ASIC design

## Slide 20: VLSI Design Flow
*process_flow* · VLSI

- [process]
  1. Physical Design: Transform logic to physical layout
  2. Floor Planning: Determine location of major blocks
  3. Placement: Locate standard cells and components
  4. Clock Distribution: Deliver clock signal to sequential elements
  5. Routing: Create metal interconnections between cells
  6. Verification: Check timing, power, and signal integrity
- [note] The physical design process is important because a logical correct circuit may still fail to meet its performance or power requirement

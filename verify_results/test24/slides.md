# test20 — 

Session 20261014-175249-401a, 16 slides.

## Slide 01: Networking (part 1)
*concept* · Networking

- **Computer networking**: the process of connecting two or more computing devices to exchange information and share resources
- Fundamentals include connecting computers, smartphones, servers, printers, and other devices
- **Sender**: the device that sends information
- **Receiver**: the device that receives information
- **Transmission medium**: the wired or wireless path to which data travel

## Slide 02: Networking (part 2)
*concept* · Networking

- **Network Devices**: Routers, Switches, Access Points and Modems
- **Protocols**: rules that allow devices to communicate

## Slide 03: OSI Model (part 1)
*key_points* · Networking

- Networking uses a 7‑layer OSI model
- Physical layer transmits bits via cables or wireless signals
- Data link layer handles local link communication; Ethernet is an example
- Network layer handles logical addressing and routing
- [image] OSI model layers (CC BY-SA 4.0)

## Slide 04: OSI Model (part 2)
*key_points* · Networking

- Transport layer provides transport services
- TCP provides reliable ordered delivery
- UDP provides connectionless transport service
- Session layer manages communication sessions
- Internet Protocol operates at this layer
- Presentation layer handles data formatting and encoding
- [image] OSI layers diagram (Public domain)

## Slide 05: OSI Model (part 3)
*members* · Networking

- **Application layer**: Provides network services used by applications such as web browsing and domain name resolution
- [image] OSI layers diagram (Public domain)
- Helps engineers understand communication processes
- Helps troubleshoot network problems systematically

## Slide 06: TCP/IP Model
*key_points* · Networking

- IP model used for Internet communication
- [image] TCP/IP model diagram (CC BY-SA 4.0)
- **TCP/IP protocol suite**: foundation of communication across the internet
- Application layer protocols: sjtp, dns, smdp
- Transport layer: TCP provides reliable ordered delivery; UDP provides unreliable datagram delivery
- Internet Layer: IP addressing and packet forwarding
- Network Access Layer uses Ethernet and Wi-Fi technologies
- Datagram delivery without TCP is built in reliability and ordering guarantees

## Slide 07: IP Addressing and Subnetting (part 1)
*members* · Networking

- **IP address**: A logical address used to identify a network interface for communication using the Internet protocol
- [image] IP Addressing and Subnetting layers (Public domain)
- [hierarchy]
  - IP Address Versions
    - IPv4
    - IPv6
- IPv4 Address Length: 32 bits
- IPv4 Notation: Dotted decimal
- IPv6 Address Length: 128 bits
- IPv6 Notation: Hexadecimal groups

## Slide 08: IP Addressing and Subnetting (part 2)
*example* · Networking

- [example] 192.168.1.10; 2001:db8::10
- [image] IP Addressing and Subnetting layers (Public domain)
- **Subnet mask**: Identifies the network portion of an IPv4 address
- [example] 192.168.1.0/24 contains 256 addresses (192.168.1.0–192.168.1.255)
- 254 usable host addresses in /24 subnet
- Network and broadcast addresses are reserved
- Organize network devices
- Manage address space
- Separate networks

## Slide 09: Networking
*concept* · Networking

- **Router**: Connects different IP networks and forwards packets to destinations
- **Network Switch**: Connects local devices and forwards Ethernet frames using MAC addresses
- **Hub**: Repeats incoming signals to all other ports without intelligent forwarding
- **Wireless Access Point**: Allows wireless devices to connect to a network using Wi-Fi
- **Modem**: Performs signal conversion or modulation for communication technology
- **Firewall**: Filters network traffic according to configured security policies
- Devices provide network connectivity
- Devices enable communication
- Devices protect network infrastructure

## Slide 10: Network Topology (part 1)
*definition* · Networking

- **Network Topology**: Describes how devices and network links are arranged
- [image] Network Topology layers (CC BY-SA 4.0)
- *Common Network Topologies*
- Star: Devices connect to a central switch or hub
- Bus: Devices share a common communication backbone
- Ring: Devices connect in a logical or physical ring
- Mesh: Devices have multiple interconnections

## Slide 11: Network Topology (part 2)
*members* · Networking

- **Hybrid Topology**: Devices are arranged in odd hierarchy
- [image] Network Topology layers (CC BY-SA 4.0)

## Slide 12: How Domain Names Work (part 1)
*definition* · DNS

- **DNS**: Translates domain names into IP addresses
- Internet Services, most commonly IP addresses

## Slide 13: How Domain Names Work (part 2)
*process_flow* · DNS

- [process]
  1. User enters a domain name
  2. Device checks local DNS cache
  3. DNS query sent to resolver if needed
  4. Resolver obtains required DNS record
  5. Browser connects to destination service using IP address
- DNS supports other record types
- MX records are used for mail routing

## Slide 14: Wi-Fi (part 1)
*definition* · Networking

- **Wi-Fi**: Family of wireless networking technologies based on IEEE 802.11 standards
- Uses radio waves instead of Ethernet cables
- Home networks use wireless routers or access points
- [hierarchy]
  - Wi-Fi Frequency Bands
    - 2.4 GHz
    - 5 GHz
    - 6 GHz

## Slide 15: Wi-Fi (part 2)
*concept* · Networking

- **SSID**: The network name
- **Access Point**: Device providing wireless network access
- Authentication and encryption protect wireless communications
- Walls and other devices can affect performance

## Slide 16: Network Security and Firewalls
*concept* · Networking

- **Firewall**: Filters traffic based on configured rules
- **Encryption**: Protects information by making it unreadable to parties without keys
- **Authentication**: Verifies the identity of a user or device
- **Network Segmentation**: Separates the network into sections to limit incident spread
- Network segmentation limits incident spread
- Common threats: phishing, malware, DoS, unauthorized access, misconfigurations
- Security requires multiple layers of protection

# Networked Systems Coursework: Reliable Transport Protocol

## Overview

In this coursework, the goal is to design and implement the server side of a custom
client-server protocol for DistroNet, a company specializing in efficient file
distribution over a private network. The challenge involves developing a protocol
that operates over UDP to ensure reliability and performance, optimizing for DistroNet’s
upgraded network infrastructure.

This directory includes all the files needed for you to complete COMP0023 coursework 1:
- server.py, implemented solution for the server side of the protocol;
- client.py, a simplified model of client side communicating with your server;
- run_tests.py, a script that runs the tests described in the coursework description;
- server_file.txt, the file to be transferred from the server to connecting clients;
- warmup-task.txt, the file that you will have to analyse to complete the warmup task of the coursework;
- baseline-traces/, a directory with the output of some tests performed with the baseline solution against which your server will be evaluated;
- baseline-metrics.txt, a file that specifies the baseline metrics for the tests in the baseline/ directory: those metrics will be used to mark your server;
- this readme file.
- coursework_description.pdf, the full description of the coursework.

## Problem Statement

As part of DistroNet's initiative to revamp their file delivery system, the task is
to reconstruct the server-side application protocol used for text file transfers.
The solution must be built atop UDP, providing a foundation to select and implement
mechanisms that guarantee packet delivery reliability and optimize performance.
Despite the server improvements, the server must remain compatible with existing
client software, which dictates the format and semantics of the packets exchanged.
Full problem statement can be found [here](./coursework_description.pdf).

## Protocol

The developed server is responsible for transferring a single file to clients
upon request. Server operation begins by listening for incoming requests on
a specific port. The file transfer process is initiated by a client's GET request,
triggering the server to send the file's content line by line, with each line sent
in a separate packet. The client acknowledges receipt with cumulative ACKs,
indicating the sequence number of the last line received in order.
The transfer is concluded with a server-sent FIN message, the client's ACK FIN response,
and the server's final ACK to close the connection.

### Message Format

The messages exchanged adhere to a fixed format utilizing reserved characters and keywords:

- **Server messages:**
  - `[client-ID] sequence-number:fileline|checksum(fileline)` (For file line transfer)
  - `[client-ID] FIN` (To indicate end of file transfer)
  - `[client-ID] ACK` (Final acknowledgement after ACK FIN)

- **Client messages:**
  - `[client-ID] GET` (Request to start file transfer)
  - `[client-ID] ACK sequence-number` (Acknowledgement of received file line)
  - `[client-ID] ACK FIN` (Acknowledgement of FIN message)

### Additional Messages

DistroNet's network devices employ ECN to signal potential congestion before dropping packets.
The server may receive ECN-marked packets that include the prefix "ECN dropped"
followed by a message it had previously sent. Upon detecting an ECN message,
the server should reduce its send rate to alleviate the congestion.

## Solution Approach

The `server.py` script incorporates sophisticated features to emulate TCP-like reliability over UDP, which inherently does not provide delivery assurance. Key features of this implementation include:

### Timers for Packet Loss Detection

The server utilizes a timer mechanism similar to TCP to detect packet loss. This mechanism is based on measuring the round-trip time (RTT) of packets. An RTT sample is taken when an acknowledgment (ACK) is received, updating the estimated RTT and deviation as follows:

- **RTT Estimation:** The server calculates a weighted average of the sample RTT and the existing estimated RTT, with a preference for recent measurements to adapt to changing network conditions.

- **Deviation Estimation:** The server computes the difference between the sample RTT and the estimated RTT to get the deviation sample. It then calculates a weighted average for the deviation, allowing for dynamic timeout adjustment.

- **Timeout Adjustment:** The timeout interval is set to the estimated RTT plus a multiple of the estimated deviation, which balances between responsiveness and stability.

Here's the implemented code snippet that calculates these values:

```python
rtt_sample = time.time() - self.time_sent[new_ack]
self.rtt = NEW_RTT_WEIGHT * rtt_sample + (1 - NEW_RTT_WEIGHT) * self.rtt if self.rtt else rtt_sample

deviation_sample = abs(rtt_sample - self.rtt)
self.deviation = NEW_DEVIATION_WEIGHT * deviation_sample + (1 - NEW_DEVIATION_WEIGHT) * self.deviation if self.deviation else deviation_sample

self.timeout_s = self.rtt + DEVIATIONS_IN_TIMEOUT * self.deviation
```

### Fast Retransmit on 3 Duplicate ACKs
The server implements a fast retransmit feature upon receiving three consecutive
duplicate ACKs. This behavior mimics TCP's fast retransmit, which is triggered by the
reception of multiple duplicate ACKs as a hint of packet loss. DistroNet’s devices may
detect losses and send bursts of duplicate ACKs, allowing the server to infer loss and
react quickly.

### Congestion Control
- **Initial Values:** The congestion window is initialized at `INITIAL_CWND` and the slow start threshold at `INITIAL_SSTHRESH`. These values dictate the rate at which the server starts data transmission and adjusts its sending rate in response to network conditions.

- **Incrementing `cwnd`:** The server increments `cwnd` by 1 only after it receives a number of ACKs equal to the current size of `cwnd`. This approach avoids the aggressive initial growth seen in TCP's slow start, instead adopting a gradual increase of the congestion window tied directly to the rate of ACK reception.

- **Transitioning from Slow Start to Avoidance:** The server initially increases `cwnd` incrementally, but once the window size reaches `ssthresh`, it takes a more conservative approach. After receiving `ACKS_ON_MAX_WINDOW_THRESHOLD` number of ACKs while at the maximum window size, `ssthresh` is incremented, and `cwnd` is reset to this new threshold value.

- **ECN Handling:** Upon receiving an ECN message indicating congestion, the server's response is to preemptively reduce the sending rate. It sets `ssthresh` to one less than `cwnd` (ensuring it's not less than 1), and `cwnd` is reduced accordingly to quickly adapt to the change in network traffic.

Here's how the server manages the congestion window in the presence of ACKs:

```python
# After receiving ACKs for all sent packets within the current window size
if self.acks_received >= self.cwnd:
    # If the congestion window is below the threshold, it's in slow start mode
    if self.cwnd < self.ssthresh:
        self.cwnd += 1  # Exponential growth phase: increment `cwnd` for each full window of ACKs
    else:
        # Once the threshold is reached or exceeded, increment `ssthresh` after a set number of ACKs
        self.acks_on_max_window += 1
        if self.acks_on_max_window >= ACKS_ON_MAX_WINDOW_THRESHOLD:
            self.ssthresh += 1  # Linear growth phase: increment `ssthresh` based on ACKs on full window
            self.cwnd = self.ssthresh  # Adjust `cwnd` to the new `ssthresh`
    self.acks_received = 0  # Reset ACK counter after updating window sizes
    self.acks_on_max_window = 0  # Reset the counter for ACKs received on max window size
```


## Evaluation

The server's performance is rigorously evaluated against a baseline solution
under various network conditions. The evaluation focuses on the server's ability
to ensure reliable data transfer, quickly retransmit lost packets, and efficiently
handle congestion.

### Test suite
- **Reliability:** The server's reliability is tested in scenarios without network
bottlenecks through tests A1, A2, and A3. The server must guarantee accurate and
complete packet delivery in the face of packet loss.
- **Fast Retransmit:** The implementation of fast retransmit is evaluated using tests
B1, B2, and B3. The server is required to detect and retransmit lost packets promptly,
regardless of the bottleneck size.
- **Fixed-Size Bottleneck Congestion:** Congestion control is assessed with tests
C1, C2, and C3. The server should minimize congestion when facing fixed-size network
bottlenecks.
- **Variable-Size Bottleneck Congestion:** Tests D1, D2, and D3 examine the server's
capability to adapt to bottlenecks that change size during a file transfer.


### Running the Tests to evaluate the server:

Start the server by executing:
```bash
python3 server.py
```
To perform the tests, run the following command on a separate command line:
```bash
python3 run_tests.py
```
To conduct a custom test without baseline comparison, use:
```bash
python3 client.py {-options}
```
This solution has been shown to **exceed the baseline in all provided tests across
every evaluated metric**, ensuring high performance in data reliability,
loss detection and retransmission, and congestion management.

Use the run_tests.py script for a comprehensive evaluation against the baseline.
The client.py script allows for custom test scenarios to further probe the server's
capabilities under specific conditions.

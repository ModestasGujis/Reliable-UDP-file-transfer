#! /usr/bin/python3

import sys, socket, subprocess, hashlib, re, time
from optparse import OptionParser, OptionValueError
import threading

# default parameters
default_ip = '127.0.0.1'
default_port = 40023
default_server_string = "127.0.0.1:50023"
default_outfile_string = "client_file.txt"
default_queuing_delay = 0.1

# constants
ECN_preamble="ECN dropped"

######################
# Network processing #
######################

class PacketProcessor:
  def __init__(self):
    self.client_packets = 0
    self.dropclientpkts = []
    self.server_packets = 0
    self.dropserverpkts = []

  def set_client_pkts_to_drop(self,listpktsno):
    self.dropclientpkts = listpktsno

  def set_server_pkts_to_drop(self,listpktsno):
    self.dropserverpkts = listpktsno

  def change_ack_number(self,data,value_change):
    m = re.match(".*ACK (\d+).*",data.decode())
    ackno = m.group(1)
    return data.decode().replace("ACK {}".format(ackno),"ACK {}".format(int(ackno)+value_change),1).encode()

  def process_client_packet(self,data):
    self.client_packets += 1
    if str(self.client_packets) in self.dropclientpkts:
      return None
    return data

  def process_server_packet(self,data):
    client_address_list = data.decode().split("]")[0].lstrip("[").split(":")
    client_address = (client_address_list[0],int(client_address_list[1]))
    payload = data.decode().split("]")[1]
    new_data = data
    self.server_packets += 1
    if str(self.server_packets) in self.dropserverpkts:
      new_data = None
    return (client_address,new_data)

#####################
# Network buffering #
#####################

class PacketBuffer:
  def __init__(self):
    self.set_size(sys.maxsize)
    self.queue = []

  def set_size(self,num_packets):
    self.size = max(num_packets,1)
    self.reset_available_space()

  def get_size(self):
    return self.size

  def reset_available_space(self):
    self.available_space = self.size

  def enqueue(self, data, sender_address):
    textdata = data.decode().strip()
    send_back = False
    # if sender_address == server_address:
      # print(f"trying to enqueue data {data}, available space {self.available_space}\n")

    if self.available_space <= 0:
      textdata = "{} {}".format(ECN_preamble,textdata)
      send_back = True
    self.queue.append((textdata.encode(),sender_address,send_back))
    self.available_space -= 1

  def dequeue(self):
    queued_data = list(self.queue)
    self.queue = []
    self.reset_available_space()
    return queued_data

  def is_empty(self):
    return len(self.queue) == 0

  def __str__(self):
    return str(self.queue)

  def __repr__(self):
    return str(self)

##########
# Client #
##########

class Client:
  def __init__(self,own_ipaddr,own_port):
    msg_preamble = "\[[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:[0-9]+\]"
    self.server_syntax = re.compile(r'({} )?{} (FIN|ACK|[a-zA-Z0-9]+:.*\|.*)$'.format(ECN_preamble,msg_preamble))
    self.received = ""
    self.ownipaddr = own_ipaddr
    self.ownport = own_port
    self.own_id = "{}:{}".format(ownipaddr,ownport)
    self.last_acked = -1
  
  def set_failed_transfer(self):
    self.received = ""

  def get_open_message(self):
    return "[{}] GET".format(self.own_id)

  def start_transfer(self,client_buffer):
    packet = self.get_open_message().encode()
    client_buffer.enqueue(packet,(self.ownipaddr,self.ownport))
    return packet

  def process_server_packet(self,data,client_buffer):
    transfer_finished = False
    print("Received (in client) {}".format(data))
    if not self.server_syntax.match(data.decode().strip().replace("\n","")):
      print("Discarded packet {} because it does not have a valid syntax".format(data))
    else:
      conndata = data.decode().split("]")[0]  
      msg = data.decode().split("]")[1]
      metadata = msg.split(":")[0].strip()
      tosend = "[{}] ACK {}".format(self.own_id,metadata)
      if msg.strip() == "ACK":
        transfer_finished = True
      elif msg.strip() != "FIN":
        try:
          seqno = int(metadata)
        except ValueError as e:
          print("Discarded packet {} because sequence number {} is not an integer".format(msg,metadata))
          return transfer_finished
        payload = ":".join(msg.split(":")[1:])
        (content,checksum) = payload.split("|")
        if seqno != self.last_acked + 1 or not check_integrity(content,checksum):
          tosend = "[{}] ACK {}".format(self.own_id,self.last_acked)
        else:
          self.received += content.split("\n")[0] + "\n"
          self.last_acked = seqno
      if not transfer_finished:
        client_buffer.enqueue(tosend.encode(),(self.ownipaddr,self.ownport))
    return transfer_finished

  def write_file(self,outfilename):
    with open(outfilename,"w") as f:
      f.write(self.received)

####################
# Helper functions #
####################

def _get_id(socket_address):
  return "[{}:{}]".format(socket_address[0],socket_address[1])

def check_integrity(string,checksum):
  return checksum == hashlib.md5(string.encode()).hexdigest()

def check_port(option, opt_str, value, parser):
  if value < 32768 or value > 61000:
    raise OptionValueError("need 32768 <= port <= 61000")
  parser.values.port = value

def check_address(option, opt_str, value, parser):
  value_array = value.split(".")
  if len(value_array) < 4 or \
     int(value_array[0]) < 0 or int(value_array[0]) > 255 or \
     int(value_array[1]) < 0 or int(value_array[1]) > 255 or \
     int(value_array[2]) < 0 or int(value_array[2]) > 255 or \
     int(value_array[3]) < 0 or int(value_array[3]) > 255:
    raise OptionValueError("IP address must be specified as [0-255].[0-255].[0-255].[0-255]")
  parser.values.ip = value

def setup_option_parser():
  parser = OptionParser(add_help_option=False)
  parser.add_option("-p", "--port", dest="port", type="int", action="callback",
                    callback=check_port, metavar="PORTNO", default=default_port,
                    help="UDP port to listen on (default: {})".format(default_port))
  parser.add_option("-a", "--address", dest="ip", type="string", action="callback",
                    callback=check_address, metavar="IPNO", default=default_ip,
                    help="IP port to listen on (default: {})".format(default_ip))
  parser.add_option("-s", "--server-address", dest="srv_addr_string", type="string",
                    action="store", default=default_server_string,
                    help="server address (default: {})".format(default_server_string))
  parser.add_option("-o", "--output-file", dest="outfile_string", type="string",
                    action="store", default=default_outfile_string,
                    help="output filename (default: {})".format(default_outfile_string))
  parser.add_option("--drop-client-packets", dest="dropclpkts", type="string", action="store", default=None)
  parser.add_option("--drop-server-packets", dest="dropsrvpkts", type="string", action="store", default=None)
  parser.add_option("--generate-three-dup-acks", dest="threeacks", type="string", action="store", default="")
  parser.add_option("--set-queue-delay", dest="queuingdel", type="string", action="store", default=None)
  parser.add_option("--set-server-buffer-size", dest="srvbuffersize", type="int", action="store", default=None)
  parser.add_option("--set-server-buffer-size-changes", dest="srvbufferchanges", type="string", action="store", 
                    default="", help="specification of buffer size changes with format: \
                    'change_modifier1'@'round_with_server_packets1',...,'change_modifierN'@'round_with_server_packetN' \
                    (e.g., +1@2,-2@5)")
  return parser

def setup_packet_processor(options):
  network_processing = PacketProcessor()
  if options.dropclpkts:
    clientpkts2drop = list(options.dropclpkts.split(","))
    network_processing.set_client_pkts_to_drop(clientpkts2drop)
  if options.dropsrvpkts:
    serverpkts2drop = list(options.dropsrvpkts.split(","))
    network_processing.set_server_pkts_to_drop(serverpkts2drop)
  return network_processing

def setup_buffers(options):
  server_buffer_changes = dict()
  client_buffer = PacketBuffer()
  server_buffer = PacketBuffer()
  if options.srvbuffersize:
    server_buffer.set_size(int(options.srvbuffersize))
  if len(options.srvbufferchanges) > 0:
    for substring in options.srvbufferchanges.split(","):
      entity = int(substring.split("@")[0].strip())
      server_packet = int(substring.split("@")[1].strip())
      server_buffer_changes[server_packet] = entity
  queuing_delay = default_queuing_delay
  if options.queuingdel:
    queuing_delay = float(options.queuingdel)
  return (client_buffer,server_buffer,server_buffer_changes,queuing_delay)

def simulate_network_queuing(queuing_delay,client_buffer,server_buffer):
  init_time = time.time()
  run_queuing_cycle(init_time,queuing_delay,client_buffer,server_buffer)

def run_queuing_cycle(init_time,queuing_delay,client_buffer,server_buffer):
  try:
    elapsed_time = 0
    while elapsed_time <= queuing_delay:
      if queuing_delay > 0:
        sock.settimeout(queuing_delay - elapsed_time)
      (data, sender_address,) = sock.recvfrom(512)
      if sender_address != server_address:    # data from client
        client_buffer.enqueue(data, sender_address)
      else:                                   # data from server
        server_buffer.enqueue(data, sender_address)
      elapsed_time = time.time() - init_time
  except socket.timeout:
    pass

start_time = None
finish_time = None

def output_stats():
  print("\nStats for file transfer")
  diffcmd = subprocess.Popen(["diff","-y","--suppress-common-lines",outfilename,"server_file.txt"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  output, errors = diffcmd.communicate()
  diffcmd.wait()
  if errors:
    raise Exception("errors while running diff:\n{}".format(errors))
  if len(output) == 0:
    print("# different lines in client file --> 0")
  else:
    output_lines = output.decode().rstrip().split("\n")
    difflines = len(output_lines)
    print("# different lines in client file --> {}".format(difflines))
    if difflines > 0:
      print("diff between client (left) and server (right) files:\n{}".format("\n".join(output_lines)))
  print("# server-triggered ECN packets --> {}".format(tot_ecn_packets))
  print("# total server packets --> {}".format(tot_srv_packets))
  print("# RTTs to complete flow --> {}".format(total_rounds))
  print("# server packets after the file transfer completed --> {}".format(additional_srv_packets))
  print("# Total time to complete transfer --> {} seconds".format(finish_time - start_time))
  sys.stdout.flush()

########
# Main #
########


if __name__ == "__main__":
  start_time = time.time()
  # parse CLI arguments
  parser = setup_option_parser()
  (options, args) = parser.parse_args()

  # process general options
  outfilename = options.outfile_string
  server_string = options.srv_addr_string
  server_address = (server_string.split(":")[0],int(server_string.split(":")[1]))

  # create a socket to receive and send out packets
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind((options.ip, options.port))
  ownipaddr, ownport = sock.getsockname()
  client_rtx_timeout = 2
  max_no_rtx = 5
  print("%s: listening on IP %s and port %d" % (sys.argv[0], ownipaddr, ownport))
  sys.stdout.flush()

  # setup client variables
  client = Client(ownipaddr,ownport)
  transfer_finished = False

  # setup network buffers and packet processing
  acks2triple = list(options.threeacks.split(","))
  network_processing = setup_packet_processor(options)
  (client_buffer,server_buffer,server_buffer_changes,queuing_delay) = setup_buffers(options)
  
  # initialise data structures for stats tracking
  client_packet_no = 0
  tot_srv_packets = 0
  tot_ecn_packets = 0
  client_in_curr_round = False
  transmission_started = False
  total_rounds = 0
  server_packet_rounds = 0

  # start transfer and process packets, simulating both queuing/congestion in the network and processing at the client
  next_rtx = time.time() + client_rtx_timeout
  curr_rtx = 0
  last_transmitted = client.start_transfer(client_buffer)
  while True:
    # print(f"Buffers before queueing client buffer: {client_buffer} server: {server_buffer}\n")
    simulate_network_queuing(queuing_delay,client_buffer,server_buffer)
    # print(f"STARTING TRANSMISSION   client buffer: {client_buffer} server: {server_buffer}\n")
    if transmission_started:
      total_rounds += 1
    # deal with cases where there is no packet to send or receive, checking if the clients want to retransmit or to give up
    if client_buffer.is_empty() and server_buffer.is_empty():
      if curr_rtx >= max_no_rtx:
        print("\nERROR: failed transfer, server not responding anymore")
        client.set_failed_transfer()
        break
      if time.time() > next_rtx:
        client_buffer.enqueue(last_transmitted,(ownipaddr,ownport))
        curr_rtx += 1
      else:
        continue
    print()
    # process data from client
    for (data,sender_address,send_back) in client_buffer.dequeue():
      transmission_started = True
      fwd_data = network_processing.process_client_packet(data)
      destination = server_address
      if send_back:
        destination = sender_address
      if fwd_data:
        last_transmitted = fwd_data
        next_rtx = time.time() + client_rtx_timeout
        client_in_curr_round = True
        if "ACK" in fwd_data.decode() and str(client_packet_no+1) in acks2triple:
          network_processing.change_ack_number(data,-1)
          for i in range(3):
            print("Forwarding {} from {} to {}".format(fwd_data,sender_address,destination))
            sock.sendto(fwd_data,destination)
            client_packet_no += 1
          break
        else:
          print("Forwarding {} from {} to {}".format(fwd_data,sender_address,destination))
          sock.sendto(fwd_data,destination)
          client_packet_no += 1
      else:
        print("Dropped client packet {}".format(data))

    # process data from server
    iteration_with_srv_packets = False
    curr_forwarded = 0
    for (origin_data,sender_address,send_back) in server_buffer.dequeue():
      client_in_curr_round = True
      (_,data) = network_processing.process_server_packet(origin_data)
      if not data:
        print("Dropped server packet {}".format(origin_data))
        continue
      if send_back:
        print("Forwarding back ECN packet {}".format(origin_data))
        sock.sendto(origin_data,server_address)
        tot_ecn_packets += 1
      elif str(client_packet_no + 1 + curr_forwarded) in acks2triple:
        print("Dropped server packet {}".format(data))
        curr_forwarded += 1
      else:
        iteration_with_srv_packets = True
        curr_rtx = 0
        curr_forwarded += 1
        transfer_finished = client.process_server_packet(data,client_buffer)
      tot_srv_packets += 1
    # adjust buffer size if needed
    if iteration_with_srv_packets:
      server_packet_rounds += 1
    if server_packet_rounds in server_buffer_changes:
      server_buffer.set_size(server_buffer.get_size() + server_buffer_changes[server_packet_rounds])
      server_buffer_changes.pop(server_packet_rounds)  # we must remove buffer size change, otherwise we would keep decreasing the buffer size until we get another server packet
    # handle terminated connections
    if transfer_finished:
      break

  # checking if the server sends us additional (useless) packets
  finish_time = time.time()
  print("\nWaiting to fully close the connection...")
  additional_srv_packets = 0
  waiting_timeout = 2
  elapsed_time = 0
  init_time = time.time()
  while waiting_timeout > elapsed_time:
    try:
      sock.settimeout(waiting_timeout - elapsed_time)
      (data, sender_address,) = sock.recvfrom(512)
      if sender_address == server_address:    # data from server
        additional_srv_packets += 1
      elapsed_time = time.time() - init_time
    except socket.timeout:
      break

  # final operations
  client.write_file(outfilename)
  output_stats()


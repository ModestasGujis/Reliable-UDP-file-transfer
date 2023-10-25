#! /usr/bin/python3

import sys, socket, hashlib
from optparse import OptionParser, OptionValueError

# default parameters
default_ip = '127.0.0.1'
default_port = 50023

####################
# Helper functions #
####################

def get_checksum(msg):
  return hashlib.md5(msg.encode()).hexdigest()

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

########
# Main #
########

if __name__ == "__main__":
  # parse CLI arguments
  # NOTE: do NOT remove support for the following options
  parser = OptionParser()
  parser.add_option("-p", "--port", dest="port", type="int", action="callback",
                    callback=check_port, metavar="PORTNO", default=default_port,
                    help="UDP port to listen on (default: {})".format(default_port))
  parser.add_option("-a", "--address", dest="ip", type="string", action="callback",
                    callback=check_address, metavar="IPNO", default=default_ip,
                    help="IP port to listen on (default: {})".format(default_ip))
  (options, args) = parser.parse_args()
  own_ip = options.ip
  own_port = options.port

  # create a socket for packet exchanges with the clients
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  own_address = (own_ip, own_port)
  sock.bind(own_address)

  # print that we are ready
  # NOTE: do NOT remove the following print
  print("%s: listening on IP %s and UDP port %d" % (sys.argv[0], own_ip, own_port))
  sys.stdout.flush()

  # extract content of file to transfer 
  content = []
  with open("server_file.txt") as f:
    content = f.readlines()

  # wait for GETs from clients, and transfer file content after each request
  while True:
    (data, sender_address,) = sock.recvfrom(512)
    client_address = data.decode().split("]")[0] + "]"
    req = data.decode().split("]")[1].strip()
    print("Received {}".format(data))
    if req == "ACK FIN":
      sock.sendto("{} ACK".format(client_address).encode(),sender_address)
    if req != "GET":
      continue

    for index in range(len(content)):
      msg = "{} {}:{}|".format(client_address,index,content[index])
      msg += get_checksum(content[index])
      sock.sendto(msg.encode(),sender_address)

    fin_msg = "{} FIN".format(client_address)
    sock.sendto(fin_msg.encode(),sender_address)


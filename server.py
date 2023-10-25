#! /usr/bin/python3

import sys, socket, hashlib, threading
from optparse import OptionParser, OptionValueError

# default parameters
default_ip = '127.0.0.1'
default_port = 50023


####################
# Helper functions #
####################

class ConcurrentSocket:
	def __init__(self, own_address, lock):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.bind(own_address)
		self.lock = lock

	def recvfrom(self, size):
		with self.lock:
			return self.sock.recvfrom(size)

	def sendto(self, msg, address):
		with self.lock:
			return self.sock.sendto(msg, address)


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


class Server:
	def __init__(self, own_address):
		self.sock = ConcurrentSocket(own_address, threading.Lock())
		self.content = []
		self.client_address = None
		self.sender_address = None
		self.last_ack = -1
		self.timers = {}

		self.timeout_s = 1

	def read_content(self, filename):
		with open(filename) as f:
			self.content = f.readlines()

	def process_ack(self, new_ack):
		for i in range(self.last_ack + 1, new_ack + 1):
			self.timers[i].cancel()
			del self.timers[i]

		self.last_ack = max(new_ack, self.last_ack)

	def send_line(self, index):
		msg = ("{} {}:{}|".format(self.client_address, index, self.content[index]) + get_checksum(
			self.content[index])).encode()
		self.sock.sendto(msg, self.sender_address)
		self.timers[index] = threading.Timer(self.timeout_s, self.send_line, [index])

	def send_fin(self):
		fin_msg = "{} FIN".format(self.client_address)
		self.sock.sendto(fin_msg.encode(), self.sender_address)

	def end_transfer(self):
		self.sock.sendto("{} ACK".format(self.client_address).encode(), self.sender_address)
		self.last_ack = -1
		for timer in self.timers:
			timer.cancel()
			del timer


	def run(self):
		# print that we are ready
		# NOTE: do NOT remove the following print
		print("%s: listening on IP %s and UDP port %d" % (sys.argv[0], own_ip, own_port))
		sys.stdout.flush()

		while True:
			(data, self.sender_address) = self.sock.recvfrom(512)
			self.client_address = data.decode().split("]")[0] + "]"
			req = data.decode().split("]")[1].strip()
			print("Received {}".format(data))
			if req == "ACK FIN":
				self.end_transfer()
			elif req[:3] == "ACK":
				ack = int(req.split(" ")[1])

				self.process_ack(ack)

				if ack == len(self.content) - 1:
					# all lines received
					self.send_fin()
				else:
					self.send_line(ack + 1)

			# set timer
			elif req == "GET":
				self.send_line(0)


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

	server = Server((own_ip, own_port))

	server.read_content("server_file.txt")

	server.run()

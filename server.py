#! /usr/bin/python3

import sys, socket, hashlib, threading, time
from optparse import OptionParser, OptionValueError

# default parameters
default_ip = '127.0.0.1'
default_port = 50023
INITIAL_SSTHRESH = 8
INITIAL_CWND = 1
INITIAL_TIMEOUT = 5

NEW_RTT_WEIGHT = 0.1
NEW_DEVIATION_WEIGHT = 0.125
DEVIATIONS_IN_TIMEOUT = 6

ACKS_ON_MAX_WINDOW_THRESHOLD = 3

TIMEOUT_INCREMENT = 0.0001
MAIN_THREAD_SLEEP_TIME = 0.000001

####################
# Helper functions #
####################

global_lock = threading.RLock()


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


def get_client_address(data):
	decoded = data.decode()
	if decoded[:3] == "ECN":
		return "[" + decoded.split("]")[0].split("[")[1] + "]"
	else:
		return decoded.split("]")[0] + "]"


class Server:
	def __init__(self, own_address):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.bind(own_address)
		self.content = []
		self.client_address = None
		self.sender_address = None
		self.transfer_in_progress = None
		self.last_ack = None
		self.duplicated_acks = None
		self.timers = None
		self.timer_updated = None
		self.timer_in_flight = None
		self.time_sent = None
		self.rtt = None
		self.deviation = None
		self.timeout_s = None
		self.ssthresh = None
		self.cwnd = None
		self.last_sent = None
		self.acks_received = None
		self.acks_on_max_window = None

		self.reset_variables()

	def reset_variables(self):
		self.client_address = None
		self.sender_address = None
		self.transfer_in_progress = False

		self.last_ack = -1
		self.duplicated_acks = 0
		self.timers = {}
		self.timer_updated = {}
		self.timer_in_flight = 0  # messages in flight triggered by timer before any ACK

		# RTT, Deviation, timeout
		self.time_sent = {}
		self.rtt = None
		self.deviation = TIMEOUT_INCREMENT
		self.timeout_s = INITIAL_TIMEOUT

		self.ssthresh = INITIAL_SSTHRESH
		self.cwnd = INITIAL_CWND
		self.last_sent = -1
		self.acks_received = 0
		self.acks_on_max_window = 0

	def read_content(self, filename):
		with open(filename) as f:
			self.content = f.readlines()

	def remove_timers(self, new_ack):
		for i in range(0, new_ack + 1):
			if i in self.timers:
				self.timers[i].cancel()
				del self.timers[i]
			if i in self.timer_updated:
				del self.timer_updated[i]

	def update_timeout(self, new_ack):
		rtt_sample = time.time() - self.time_sent[new_ack]
		self.rtt = NEW_RTT_WEIGHT * rtt_sample + (1 - NEW_RTT_WEIGHT) * self.rtt if self.rtt else rtt_sample

		deviation_sample = abs(rtt_sample - self.rtt)
		self.deviation = NEW_DEVIATION_WEIGHT * deviation_sample + (1 - NEW_DEVIATION_WEIGHT) * self.deviation if self.deviation else deviation_sample

		self.timeout_s = self.rtt + DEVIATIONS_IN_TIMEOUT * self.deviation

	def process_ack(self, new_ack):
		if not self.transfer_in_progress:
			return

		self.timer_in_flight = 0
		self.acks_received += 1
		if new_ack == self.last_ack:
			self.duplicated_acks += 1
			if self.duplicated_acks == 2:
				# fast retransmit, no window check
				# from csw, doesn't imply congestion
				self.last_sent = new_ack
				self.last_ack = new_ack - 1
				self.acks_received = 0
				self.duplicated_acks = 0
				print("3 duplicates -> Fast retransmit")
				while self.transfer_in_progress and self.last_sent + 1 <= len(self.content) and new_ack + self.cwnd > self.last_sent:
					self.send_line(self.last_sent + 1)
			return
		else:
			self.duplicated_acks = 0

		self.update_timeout(new_ack)

		self.remove_timers(new_ack)

		self.last_ack = max(new_ack, self.last_ack)

		if self.acks_received >= self.cwnd:
			if self.cwnd < self.ssthresh:
				self.cwnd += 1
				self.acks_received = 0
			else:
				self.acks_on_max_window += 1
				if self.acks_on_max_window >= ACKS_ON_MAX_WINDOW_THRESHOLD:
					self.ssthresh += 1
					self.cwnd = self.ssthresh
					self.acks_received = 0
					self.acks_on_max_window = 0

		while self.transfer_in_progress and self.last_sent + 1 <= len(self.content) and new_ack + self.cwnd > self.last_sent:
			self.send_line(self.last_sent + 1)

	def send_line(self, index, timer_triggered=False):
		with global_lock:  # to prevent concurrent send_line
			if timer_triggered:
				# assume a lost packet, no congestion
				if index <= self.last_ack:  # out of date timer, ignore
					print("Ignoring out of date timer")
					return

				if time.time() - self.timer_updated[index] < self.timeout_s:  # timer already updated
					print("Timer out of date, ignoring")
					return

				if self.last_ack + 1 == index:
					self.duplicated_acks = 0
				# lower last ack so it doesn't trigger fast retransmit

				self.last_sent = index
				self.acks_received = 0
				self.acks_on_max_window = 0
			# end timer triggered

			self.last_sent = max(index, self.last_sent)
			self.time_sent[index] = time.time()

			if index == len(self.content):
				self.send_fin()
				return
			elif index == len(self.content) + 1:
				self.end_transfer()
				return

			self.timer_in_flight += int(timer_triggered)

			msg = ("{} {}:{}|".format(self.client_address, index, self.content[index]) + get_checksum(
				self.content[index])).encode()
			self.sock.sendto(msg, self.sender_address)
			if index in self.timers:
				self.timers[index].cancel()
			self.timers[index] = threading.Timer(self.timeout_s, self.send_line, [index, True])
			self.timers[index].start()
			self.timer_updated[index] = time.time()

			# increment timout slightly so that we don't get out of order triggers
			self.timeout_s += TIMEOUT_INCREMENT

	def start_transfer(self):
		self.transfer_in_progress = True
		for i in range(self.cwnd):
			self.send_line(i)

	def send_fin(self):
		fin_msg = "{} FIN".format(self.client_address)
		self.sock.sendto(fin_msg.encode(), self.sender_address)

	def end_transfer(self):
		if not self.transfer_in_progress:
			return
		print("Ending transfer")
		self.transfer_in_progress = False
		self.sock.sendto("{} ACK".format(self.client_address).encode(), self.sender_address)

		for i in list(self.timers):
			self.timers[i].cancel()
			del self.timers[i]
			if i in self.timer_updated:
				del self.timer_updated[i]
		self.reset_variables()

	def process_ecn(self, data):
		if not self.transfer_in_progress:
			return
		self.ssthresh = max(self.cwnd - 1, 1)
		self.cwnd = max(1, self.ssthresh - 1)
		msg = data.decode().split("]")[1].strip()
		if msg == "FIN":
			ack_returned = len(self.content)
		elif msg == "ACK":
			ack_returned = len(self.content) + 1
		else:
			ack_returned = int(msg.split(":", 1)[0])

		self.last_sent = ack_returned - 1
		self.acks_on_max_window = 0
		self.acks_received = 0

		for i in range(max(0, self.cwnd - self.timer_in_flight)):
			if not self.transfer_in_progress or ack_returned + i > len(self.content) + 1:
				break
			self.timer_in_flight += 1
			self.send_line(ack_returned + i)

	def run(self):
		# NOTE: do NOT remove the following print
		print("%s: listening on IP %s and UDP port %d" % (sys.argv[0], own_ip, own_port))
		sys.stdout.flush()

		while True:
			with global_lock:
				(data, self.sender_address) = self.sock.recvfrom(512)
				self.client_address = get_client_address(data)
				req = data.decode().split("]")[1].strip()

				if req == "ACK FIN":
					if self.last_ack != -1:  # prevent processing ack fin twice
						self.end_transfer()
				elif data.decode()[:3] == "ECN":
					self.process_ecn(data)
				elif req[:3] == "ACK":
					ack = int(req.split(" ")[1])
					self.process_ack(ack)
				elif req == "GET":
					self.start_transfer()
			time.sleep(MAIN_THREAD_SLEEP_TIME)  # prevent timer starvation


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

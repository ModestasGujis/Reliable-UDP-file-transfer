import subprocess

tests = [
	['A1', 'python3 client.py --set-queue-delay=0.1 --drop-server-packets=4', 0, 0, 1000, 1000, 0],
	['A2', 'python3 client.py --set-queue-delay=0.1 --drop-client-packets=6', 0, 0, 1000, 1000, 0],
	['A3', 'python3 client.py --set-queue-delay=0.1 --drop-server-packets=1,17', 0, 0, 1000, 1000, 0],

	['B1', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=10 --generate-three-dup-acks=9', 0, 0, 26,
	 15, 0],
	['B2', 'python3 client.py --set-queue-delay=1 --set-server-buffer-size=10', 0, 0, 22, 13, 0],
	['B3', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=1 --generate-three-dup-acks=4', 0, 0, 32,
	 58, 0],

	['C1', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3', 0, 1, 23, 17, 0],
	['C2', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3 --drop-server-packets=5', 0, 1, 25, 29,
	 0],
	['C3', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=2 --generate-three-dup-acks=3', 0, 3, 30,
	 34, 0],

	['D1', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=1 --set-server-buffer-size-changes=2@5', 0,
	 3, 25, 23, 0],
	['D2', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3 --set-server-buffer-size-changes=-2@8',
	 0, 6, 29, 41, 0],
	['D3',
	 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3 --drop-server-packets=3 --set-server-buffer-size-changes=5@6',
	 0, 1, 24, 29, 0],
]

HEADER = '\033[95m'
FAIL = '\033[91m'
OKGREEN = '\033[92m'
ENDC = '\033[0m'
OKBLUE = '\033[94m'

def get_result(test, my_result):
	return f"{OKGREEN}PASSED{ENDC}" if test >= my_result else f"{FAIL}FAILED{ENDC}"


metric_names = [
	'# different lines in client file --> {} test: {}, me: {}',
	'# server-triggered ECN packets   --> {} test: {}, me: {}',
	'# total server packets           --> {} test: {}, me: {}',
	'# RTTs to complete flow          --> {} test: {}, me: {}',
	'# server packets after completed --> {} test: {}, me: {}',
]

good = 0
for test in tests:
	print(f"{HEADER}Running test {test[0]}{ENDC}")
	result = subprocess.run('python3 client.py --set-queue-delay=0.1 --drop-server-packets=4',
	                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True,
	                        text=True).stdout.split('\n')

	for i in range(0, 5):
		res = get_result(test[2 + i], int(result[-7 + i].split(' ')[-1]))
		good += (res == f"{OKGREEN}PASSED{ENDC}")
		print(metric_names[i].format(res, test[2 + i], result[-7 + i].split(' ')[-1]))

	print(f"# Time taken: {OKBLUE}{' '.join(result[-2].split(' ')[-2:])}{ENDC}")

print(f"Passed {good} tests our of {len(tests) * 5}")

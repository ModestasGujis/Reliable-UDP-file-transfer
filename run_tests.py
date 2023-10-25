import subprocess

tests = [
	['A1', 'python3 client.py --set-queue-delay=0.1 --drop-server-packets=4', 0, 0, 1000, 1000, 0],
	['A2', 'python3 client.py --set-queue-delay=0.1 --drop-client-packets=6', 0, 0, 1000, 1000, 0],
	['A3', 'python3 client.py --set-queue-delay=0.1 --drop-server-packets=1,17', 0, 0, 1000, 1000, 0],

	['B1', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=10 --generate-three-dup-acks=9', 0, 0, 26, 15, 0],
	['B2', 'python3 client.py --set-queue-delay=1 --set-server-buffer-size=10', 0, 0, 22, 13, 0],
	['B3', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=1 --generate-three-dup-acks=4', 0, 0, 32, 58, 0],

	['C1', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3', 0, 1, 23, 17, 0],
	['C2', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3 --drop-server-packets=5', 0, 1, 25, 29, 0],
	['C3', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=2 --generate-three-dup-acks=3', 0, 3, 30, 34, 0],

	['D1', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=1 --set-server-buffer-size-changes=2@5', 0, 3, 25, 23, 0],
	['D2', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3 --set-server-buffer-size-changes=-2@8', 0, 6, 29, 41, 0],
	['D3', 'python3 client.py --set-queue-delay=0.1 --set-server-buffer-size=3 --drop-server-packets=3 --set-server-buffer-size-changes=5@6', 0, 1, 24, 29, 0],
]

FAIL = '\033[91m'
OKGREEN = '\033[92m'
ENDC = '\033[0m'

good = 0
for test in tests:
	print("Running test " + test[0])
	result = subprocess.run('python3 client.py --set-queue-delay=0.1 --drop-server-packets=4',
	                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, check=True,
	                        text=True).stdout.split('\n')

	res = f"{OKGREEN}PASSED{ENDC}" if test[2] >= int(result[-7].split(' ')[-1]) else f"{FAIL}FAILED{ENDC}"
	good += (res == f"{OKGREEN}PASSED{ENDC}")
	print('# different lines in client file --> {} test: {}, me: {}'.format(res, test[2], result[-7].split(' ')[-1]))

	res = f"{OKGREEN}PASSED{ENDC}" if test[3] >= int(result[-6].split(' ')[-1]) else f"{FAIL}FAILED{ENDC}"
	good += (res == f"{OKGREEN}PASSED{ENDC}")
	print('# server-triggered ECN packets   --> {} test: {}, me: {}'.format(res, test[3], result[-6].split(' ')[-1]))

	res = f"{OKGREEN}PASSED{ENDC}" if test[4] >= int(result[-5].split(' ')[-1]) else f"{FAIL}FAILED{ENDC}"
	good += (res == f"{OKGREEN}PASSED{ENDC}")
	print('# total server packets           --> {} test: {}, me: {}'.format(res, test[4], result[-5].split(' ')[-1]))

	res = f"{OKGREEN}PASSED{ENDC}" if test[5] >= int(result[-4].split(' ')[-1]) else f"{FAIL}FAILED{ENDC}"
	good += (res == f"{OKGREEN}PASSED{ENDC}")
	print('# RTTs to complete flow          --> {} test: {}, me: {}'.format(res, test[5], result[-4].split(' ')[-1]))

	res = f"{OKGREEN}PASSED{ENDC}" if test[6] >= int(result[-3].split(' ')[-1]) else f"{FAIL}FAILED{ENDC}"
	good += (res == f"{OKGREEN}PASSED{ENDC}")
	print('# server packets after completed --> {} test: {}, me: {}'.format(res, test[6], result[-3].split(' ')[-1]))
	print("# Time taken: {}".format(' '.join(result[-2].split(' ')[-2:])))

print(f"Passed {good} tests our of {len(tests) * 5}")
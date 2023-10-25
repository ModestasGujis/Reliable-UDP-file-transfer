# Overview
This directory includes all the files needed for you to complete COMP0023 coursework 1:
- server.py, a skeleton of the server you are asked to implement;
- client.py, a simplified model of client side communicating with your server;
- server_file.txt, the file to be transferred from the server to connecting clients;
- warmup-task.txt, the file that you will have to analyse to complete the warmup task of the coursework;
- baseline-traces/, a directory with the output of some tests performed with the baseline solution against which your server will be evaluated;
- baseline-metrics.txt, a file that specifies the baseline metrics for the tests in the baseline/ directory: those metrics will be used to mark your server;
- this readme file.

# Test your server
The simplest way to test your server is to run the server in one terminal and the client in another.
Assuming that the default IPs and ports are set consistently across the server and client, you can do so by executing the following commands:
  (CLI1) $ python3 server.py
  (CLI2) $ python3 client.py


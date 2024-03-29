#!/usr/bin/env python3

import argparse

import serial
import socket
import sys
import os
import time
import datetime
import struct
import threading
import queue
import re
import copy
import select
import logging

import tdf3
import ListenClient

from PacpMessage import PayloadType, DecryptionError
from NodeFilter import NodeFilter
from MessageTransport import PacpTransportSerial, PacpTransportSocket
import PacpMessage


class ScreenOutput():

    def __init__(self, settings):
        self.tprev = time.localtime(0)
        self.show_tx = 't' in settings
        self.show_rx = 'r' in settings
        self.show_dbg = 'd' in settings
        self.show_hdr = 'h' in settings
        if 'c' in settings:
            self.BLACK = '\033[90m'
            self.RED = '\033[91m'
            self.GREEN = '\033[92m'
            self.YELLOW = '\033[93m'
            self.BLUE = '\033[94m'
            self.PURPLE = '\033[95m'
            self.CYAN = '\033[96m'
            self.GREY = '\033[97m'
            self.END = '\033[0m'
        else:
            self.BLACK = ''
            self.RED = ''
            self.GREEN = ''
            self.YELLOW = ''
            self.BLUE = ''
            self.PURPLE = ''
            self.CYAN = ''
            self.GREY = ''
            self.END = ''

    def print_tx(self, packet):
        if self.show_tx:
            self.print_packet("tx", packet)

    def print_rx(self, packet):
        if self.show_rx:
            self.print_packet("rx", packet)

    def print_packet(self, mode, packet):
        tnow = time.localtime(time.time())
        if (tnow[3] != self.tprev[3]):
            print(time.strftime('======= %A %d-%b-%Y ========', tnow))
            self.tprev = tnow
        if self.show_hdr:
            body = bytes(packet)
        else:
            body = packet.payload
        body_str = ' '.join(["{:02x}".format(b) for b in body])
        color = self.GREEN if mode == "rx" else self.BLUE
        # header = "RX:" if mode == "rx" else "TX:"

        # time_str = datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]
        # print("{:s}{:s} {:s}{:s} {:s}".format(color, time_str, header, self.END, body_str))


class SerialConnection():

    devices = {
        "pacp3": {
            "flow_control": True,
            "dtr_reset": True,
            "rts_high": True
        },
        "usb": {
            "flow_control": True,
            "dtr_reset": False,
            "rts_high": True
        }
    }

    def __init__(self, serial_port, baudrate, device_type):
        self.port = serial_port
        self.baud = baudrate
        self.device = self.devices[device_type]
        self.ser = None
        self.open()
        self.initialise()

    def open(self):
        self.ser = serial.Serial(self.port, self.baud, rtscts=self.device["flow_control"])
        logging.info("Serial: Using {:s}:{:d}".format(self.port, self.baud))
        time.sleep(0.2)

    def close(self):
        logging.info("Serial: Closing {:s}:{:d}".format(self.port, self.baud))
        self.ser.close()

    def initialise(self):
        # Setup DTR pin state
        self.ser.setDTR(self.device["rts_high"])
        # Reboot node if required
        if self.device["dtr_reset"]:
            self.ser.setDTR(1)
            time.sleep(0.2)
            self.ser.setDTR(0)

    def read(self, num_bytes):
        return self.ser.read(num_bytes)

    def write(self, serial_packet):
        # Prepend with 0x00 to account for the first byte being lost on USB
        self.ser.write(b"\x00" + bytes(serial_packet))


class SocketConnections():

    class ClientGroup:
        '''
        Unique group of clients identified by connection socket
        Used to distribute messages to all connections against the connection socket
        '''

        def __init__(self, connection_port):
            self._connection_port = connection_port
            self._connection_socket = self._new_socket(connection_port)
            self._clients = {}
            self._clients_lock = threading.Lock()

        def _new_socket(self, port):
            new_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            new_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            new_socket.bind(('', port))
            new_socket.listen()
            return new_socket

        def accept_connection(self, connection_socket):
            if connection_socket == self._connection_socket:
                (client_socket, (addr, port)) = self._connection_socket.accept()
                client_socket.setblocking(0)
                self._clients_lock.acquire()
                self._clients[client_socket] = {"addr": addr, "local_port": self._connection_port, "remote_port": port}
                self._clients_lock.release()
                # logging.info("Client: {:s}:{:d} connected".format(addr, port))
                return client_socket
            return None

        def distribute(self, byte_buffer):
            broken_clients = []
            self._clients_lock.acquire()
            for client in self._clients:
                try:
                    client.send(byte_buffer)
                except (socket.timeout, socket.error):
                    broken_clients.append(socket)
            for client in broken_clients:
                self.close_socket(client)
            self._clients_lock.release()

        def close(self):
            logging.info("Sockets: Closing port {:d}".format(self._connection_port))
            self._connection_socket.close()
            # Try for up to a second to acquire the lock
            # If this fails, it is likely the thread crashed while it held the lock
            acquired = self._clients_lock.acquire(True, 1.0)
            client_list = [x for x in self._clients]
            for client in client_list:
                self.close_socket(client)
            if acquired:
                self._clients_lock.release()

        def close_socket(self, sock):
            if sock in self._clients:
                try:
                    sock.shutdown(sock.SHUT_RDWR)
                except:
                    pass
                try:
                    sock.close()
                except:
                    pass
                # logging.info("Client: {:s}:{:d} disconnected".format(self._clients[sock]["addr"], self._clients[sock]["remote_port"]))
                del self._clients[sock]
                return True
            return False

        def socket_info(self, sock):
            return (self._clients[sock]["addr"], self._clients[sock]["remote_port"])

        @property
        def num_clients(self):
            return len(self._clients)

        @property
        def sockets(self):
            self._clients_lock.acquire()
            sockets = [self._connection_socket, *self._clients]
            self._clients_lock.release()
            return sockets

    def __init__(self, packet_port, debug_port):
        self.packet_group = self.ClientGroup(packet_port)
        self.debug_group = self.ClientGroup(debug_port)
        self.max_clients = 0

    def socket_recv(self):
        packets = []
        # Listen for events on all sockets we are interested in
        all_sockets = self.packet_group.sockets + self.debug_group.sockets
        readable, writable, err = select.select(all_sockets, [], [], 1.0)
        for sock in readable:
            # A new client connecting to one of our groups
            if self.packet_group.accept_connection(sock) or self.debug_group.accept_connection(sock):
                self.client_summary()
            # An existing client has had some event
            else:
                # Try and read data from socket
                try:
                    packets.append(PacpTransportSocket.receive_from(sock))
                # Check for remote connections closing
                except (ConnectionResetError, socket.timeout, socket.error):
                    if self.packet_group.close_socket(sock) or self.debug_group.close_socket(sock):
                        self.client_summary()
                    continue
                # Extract packets from the socket stream
        for sock in writable:
            logging.exception("Socket appeared in writeable list {:}".format(sock))
            if self.packet_group.close_socket(sock) or self.debug_group.close_socket(sock):
                self.client_summary()
        for sock in err:
            logging.exception("Socket appeared in error list {:}".format(sock))
            if self.packet_group.close_socket(sock) or self.debug_group.close_socket(sock):
                self.client_summary()
        return packets

    def release(self):
        try:
            self.packet_group._clients_lock.release()
        except RuntimeError:
            pass
        try:
            self.debug_group._clients_lock.release()
        except RuntimeError:
            pass

    def close(self):
        self.packet_group.close()
        self.debug_group.close()

    def client_summary(self):
        current_clients = self.packet_group.num_clients + self.debug_group.num_clients
        self.max_clients = max(self.max_clients, current_clients)
        # logging.info("Clients: now={:d}, max={:d}".format(current_clients, self.max_clients))


class Baselisten():
    def __init__(self, serial_port, baudrate, device_type, base_socket_port, show):
        self.shutdown = threading.Event()
        self.serial = SerialConnection(serial_port, baudrate, device_type)
        self.sockets = SocketConnections(base_socket_port, base_socket_port + 1)
        self.screen = ScreenOutput(show)
        self.last_rx = time.time()
        self.rx_sequence = None
        self.tx_sequence = 0
        self.serialData = ""

    def run(self):
        self.socket_thread = threading.Thread(target=self.run_sockets_receive)
        self.serial_thread = threading.Thread(target=self.run_serial_receive)

        self.socket_thread.start()
        self.serial_thread.start()

        try:
            while self.socket_thread.is_alive() and self.serial_thread.is_alive():
                time.sleep(1.0)
        except KeyboardInterrupt:
            logging.exception("KeyboardInterrupt received, killing tasks...")
        # Let the threads terminate naturally
        self.shutdown.set()
        self.sockets.release()
        # Wait a short time for threads to exit cleanly
        self.socket_thread.join(2.0)
        self.serial_thread.join(2.0)
        # Cleanup all our sockets/ports
        self.serial.close()
        self.sockets.close()

    def run_sockets_receive(self):
        logging.info('Socket handler running')
        while not self.shutdown.is_set():
            packets = self.sockets.socket_recv()
            for packet in packets:
                # Output received data to serial port
                serial_packet = PacpTransportSerial(address=packet.address, sequence=self.tx_sequence, payload_type=packet.payload_type, payload=packet.payload)
                self.screen.print_tx(serial_packet)
                self.serial.write(serial_packet)
                self.tx_sequence = (self.tx_sequence + 1) % 256
        logging.info('Socket handler exiting')

    def run_serial_receive(self):
        logging.info('Serial handler running')
        reconstructor = PacpTransportSerial.reconstruct()
        pending_line = ""

        while not self.shutdown.is_set():
            # Read the next byte off the serial port
            try:
                recv_byte = self.serial.read(1)
            except serial.SerialException as e:
                print("Failed to read bytes from serial port ({:s})".format(str(e)))
                self.shutdown.set()
                return
            next(reconstructor)
            (consumed, packet) = reconstructor.send(recv_byte)

            if not consumed:
                try:
                    char = recv_byte.decode('utf-8')
                    if char == "\n":
                        if (pending_line[0:2] == "aa"):
                            self.serialData = pending_line[2:]
                        else: 
                            print(pending_line)
                        self.sockets.debug_group.distribute(pending_line.encode('utf-8'))
                        pending_line = ""
                    else: 
                        pending_line += char

                except UnicodeDecodeError:
                    print('.', end='')

            if packet is not None:
                # Validate sequence number increasing, or more that one second has passed
                if (self.rx_sequence == packet.sequence) and ((time.time() - self.last_rx) < 1.0):
                    print("Discarding duplicate packet: Header {:s}".format(" ".join(["{:02X}".format(b) for b in bytes(packet)])))
                    self.pending_serial_packet = PacpTransportSerial()
                    continue
                self.rx_sequence = packet.sequence
                self.last_rx = time.time()

                self.screen.print_rx(packet)
                # Regenerate the serial packet as a socket packet
                socket_packet = PacpTransportSocket(address=packet.address, sequence=packet.sequence, payload_type=packet.payload_type, payload=packet.payload)
                self.sockets.packet_group.distribute(bytes(socket_packet))
        logging.info('Serial handler exiting')


def logging_init(output, level):
    LOG_DATE = '%Y-%m-%d %H:%M:%S'
    LOG_FORMAT = '%(asctime)s.%(msecs)03d %(levelname) 8s: %(message)s'
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE)
    formatter.converter = time.gmtime
    log = logging.getLogger()
    log.handlers = []

    if output in ["stdout", "out", "1"]:
        handler = logging.StreamHandler(sys.stdout)
    elif output in ["stderr", "err", "2"]:
        handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.FileHandler(os.path.abspath(output))
    handler.setFormatter(formatter)
    log.addHandler(handler)
    log.setLevel(level)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Serial listener for FreeRTOS. Receives messages from a root node via serial and distributes them to clients connected via sockets')
    parser.add_argument('--serial', '-s', dest='serial_port', type=str, default="/dev/ttyUSB0", help='Serial device to connect to')
    parser.add_argument('--device', '-d', dest='device_type', type=str, default="usb", help='Device type')
    parser.add_argument('--baudrate', '--baud', '-b', dest='baudrate', type=int, default=115200, help='Baudrate of connected device')
    parser.add_argument('--port', '-p', dest='base_socket_port', type=int, default=9001, help='Port for whole packet messages')
    parser.add_argument('--show', dest='show', type=str, default="rtc", help='show (r)x messages, (t)x messages, serial (h)eader and/or (d)ebug data in (c)olor')
    parser.add_argument('--logfile', dest='log_file', type=str, default="stderr", help='Filename to direct log messages to')
    parser.add_argument('--loglevel', dest='log_level', type=str, default="INFO", help='Filename to direct log messages to')

    args = parser.parse_args()

    logging_init(args.log_file, args.log_level)
    logging.critical("Baselisten started...")

    delattr(args, "log_file")
    delattr(args, "log_level")

    baselisten = Baselisten(**vars(args))
    baselisten.run()

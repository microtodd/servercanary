#!/usr/bin/python
#
# servercanary.py
#
# @auathor T.S. Davenport (todd.davenport@yahoo.com)
# @author Ferritt1975 (https://github.com/Ferritt1975)
#
#
from wsgiref.simple_server import make_server
from cgi import parse_qs, escape
import ConfigParser
import psutil
import socket
import daemon
import datetime
import sys
from uptime import uptime
from netifaces import interfaces, ifaddresses, AF_INET
from slackclient import SlackClient

__VERSION__ = "0.6"

## StatusChecker
#
# see README.md
#
class StatusChecker:

    # List of tests to run
    _checksToRun = []
    _errorState = False
    _lastError = ''

    ## constructor
    #
    def __init__(self, inputFile=None):

        # Init
        self._checksToRun = []
        self._errorState = False
        self._lastError = ''
        
        # List of tests for this server
        if inputFile:

            # If input file could not be opened, track this as an internal error
            try:
                myConfParser = ConfigParser.ConfigParser()
                myConfParser.read(inputFile)

                # Read the items out of the conf file
                for item in myConfParser.items('healthchecks'):
                    command = item[0]
                    arg = item[1]

                    # Check and see if item is a list
                    for subarg in str(arg).split(','):
                        self._checksToRun.append( [command,subarg] )

            except Exception as e:
                self._errorState = True
                self._lastError = 'Canary could not fly: ' + str(e)

    ## TODO notify
    #
    # Send an SNS message about something
    #
    def notify(self):
        pass

    ## main call
    #
    # @return status A Dictionary
    # {
    #   status:     'ok|error',
    #   issues:     [ list of error messages ]
    # }
    def checkServerHealth(self):

        # Check for internal errors
        if self._errorState:
            returnStatus = {}
            returnStatus['status'] = 'error'
            returnStatus['issues'] = [self._lastError]
            return returnStatus

        # List of issues
        serverIssues = []

        # Overall status
        serverOverallStatus = 'ok'

        # Do stuff
        for check in self._checksToRun:

            # ps
            if str(check[0]) == 'ps':
                status = self._checkPS(check[1])
                if not status:
                    serverIssues.append( 'ps: could not find process named \'' + str(check[1]) + '\'' )

            # port
            elif str(check[0]) == 'port':
                status = self._checkPort(check[1])
                if not status:
                    serverIssues.append( 'port: port is not bound \'' + str(check[1]) + '\'' )

            # pidfile
            elif str(check[0]) == 'pidfile':
                status = None
                try:
                    status,pid = self._checkPidFile(check[1])
                    if not status:
                        serverIssues.append( 'pidfile: pidfile \'' + str(check[1]) + '\' pid \'' + str(pid)+ '\' not found' )
                except Exception as e:
                    serverIssues.append( 'pidfile: \'' + str(check[1]) + '\': \'' + str(e) + '\'' )

            # error
            else:
                serverIssues.append( 'Unknown command: ' + check[0] + ':' + check[1] )

        # Return
        if len(serverIssues) > 0:
            serverOverallStatus = 'error'
        returnStatus = {}
        returnStatus['status'] = serverOverallStatus
        returnStatus['issues'] = serverIssues
        return returnStatus

    ## _checkPS
    #
    # @param[in] string PID to check for
    # @return boolean   Is it running
    def _checkPS(self,process):
        if process:

            # Iterate the ps table
            for proc in psutil.process_iter():
                if str(proc.name).find(str(process)) != -1:
                    return True

        # Process not found
        return False

    ## _checkPort
    #
    # @param[in] int    portnum to check
    # @return boolean   Is it bound
    def _checkPort(self,port):
        if port:
            for addr in self._ip4_addresses():
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = s.connect_ex((str(addr), int(port)))
                if result == 0:
                    s.close()
                    return True

        # Not found
        return False

    ## _ip4_addresses
    #
    # @return list of interfaces on this host
    def _ip4_addresses(self):
        ip_list = []
        for interface in interfaces():
            ifaddrs = ifaddresses(interface)
            if AF_INET in ifaddrs:
                for link in ifaddrs[AF_INET]:
                    ip_list.append(link['addr'])
        return ip_list


    ## _checkPidfile
    #
    # @param[in] string Filename
    # @return boolean,pid   PID file is valid/running and the pid itself
    def _checkPidFile(self,fileName):
        pid = ''
        if fileName:
            f = open(fileName, 'r')
            for line in f:
                pid = int(line)

            process = psutil.Process(pid)
            if process and process.status():
                return True, pid

        # Nope
        return False, pid

# Executive
def application(environ, start_response):

    # Create our StatusChecker
    sc = StatusChecker(ConfFile)

    # Check server health
    serverStatus = {}

    # Get current datetime
    dt = datetime.datetime.now()

    # Make the server status check call
    # Wrap in try/catch
    try:
        serverStatus = sc.checkServerHealth()
    except Exception as e:
        serverStatus['status'] = 'error'
        serverStatus['issues'] = ['Couldn\'t check server health: ' + str(e)]

    # Put time in return if it was asked for
    if str(ShowTime) == 'yes':
        now = str(dt) + " TZ:" + str(dt.tzname())
        serverStatus['datetime'] = now

    # Get uptime.  Put in return if asked for
    systemUptime = uptime()
    if str(ShowUptime) == 'yes':
        serverStatus['uptime'] = str(datetime.timedelta(seconds=systemUptime))

    # Check status
    status = '200 OK'
    if str(serverStatus['status']) != 'ok':
        status = '500 Internal Server Error'

        # Check if we should notify
        if SlackToken is not None and SlackChannel is not None:
            SlackChannel = '#' + SlackChannel
            sc = SlackClient(SlackToken)
            print sc.api_call("chat.postMessage", channel=str(SlackChannel), username='canary', icon_emoji=':hatched_chick:',
                text="Oh Noes!  Something bad happened! Commensing self-desctruct sequence in 5...4...3...")

    # See if we are in a "grace period"
    # If we are, always return 200
    if int(GracePeriod) > 0:
        if systemUptime <= float(GracePeriod):
            status = '200 OK'
            serverStatus['inGracePeriod'] = 'true'

    # Respond
    response_body = str(serverStatus)
    response_headers = [('Content-Type', 'text/plain'),
                        ('Content-Length', str(len(response_body)))]
    start_response(status, response_headers)
    return [response_body]

## "main"
#

# Check for command line args
PidFile = '/tmp/canaryserver.pid'
ConfFile = '/etc/canaryserver.cfg'
ListenPort = 8002
ListenHost = 'localhost'
ShowTime = False
ShowUptime = False
GracePeriod = 0
SlackToken = None
SlackChannel = None
i = 0
for arg in sys.argv:
    if str(arg) == '-f':
        ConfFile = sys.argv[i+1]
    i += 1

# Load conf file
MyConfParser = ConfigParser.ConfigParser()
MyConfParser.read(ConfFile)
if MyConfParser.has_option('main','PidFile'):
    PidFile = str(MyConfParser.get('main','PidFile'))
if MyConfParser.has_option('main','ListenPort'):
    ListenPort = str(MyConfParser.get('main','ListenPort'))
if MyConfParser.has_option('main','ListenHost'):
    ListenHost = str(MyConfParser.get('main','ListenHost'))
if MyConfParser.has_option('main','ShowTime'):
    ShowTime = str(MyConfParser.get('main','ShowTime'))
if MyConfParser.has_option('main','ShowUptime'):
    ShowUptime = str(MyConfParser.get('main','ShowUptime'))
if MyConfParser.has_option('main','GracePeriod'):
    GracePeriod = str(MyConfParser.get('main','GracePeriod'))

# Run as a daemon....detach and write out the pid file
daemon.daemonize(PidFile)
httpd = make_server(ListenHost, int(ListenPort), application)
httpd.serve_forever()


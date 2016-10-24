#
# StatusCanary.py
#
# TODO:
# -Add SNS notify
#
from wsgiref.simple_server import make_server
from cgi import parse_qs, escape
import psutil
import socket
import daemon
import datetime
import sys

__VERSION__ = "0.4"

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
                f = open(inputFile, 'r')
                for line in f:
                    command,arg = str(line).split(':')
                    self._checksToRun.append( [command,arg.rstrip('\n')] )
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
    # @param[in] none
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
                    status = self._checkPidFile(check[1])
                    if not status:
                        serverIssues.append( 'pidfile: pidfile \'' + str(check[1]) + '\' pid not found' )
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
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = s.connect_ex(('127.0.0.1', int(port)))
            if result == 0:
                s.close()
                return True

        # Not found
        return False

    ## _checkPidfile
    #
    # @param[in] string Filename
    # @return boolean   PID file is valid/running
    def _checkPidFile(self,fileName):
        if fileName:
            pid = ''
            f = open(fileName, 'r')
            for line in f:
                pid = int(line)

            process = psutil.Process(pid)
            if process and process.status():
                return True

        # Nope
        return False

# Executive
def application(environ, start_response):

    # Create our StatusChecker
    sc = StatusChecker(ConfFile)

    # Get datetime
    dt = datetime.datetime.now()
    now = str(dt) + " TZ:" + str(dt.tzname())

    # Check server health
    serverStatus = {}

    try:
        serverStatus = sc.checkServerHealth()
    except Exception as e:
        serverStatus['status'] = 'error'
        serverStatus['issues'] = ['Couldn\'t check server health: ' + str(e)]

    # Set datetime
    serverStatus['datetime'] = now
    response_body = str(serverStatus)

    # Check status
    status = '200 OK'
    if str(serverStatus['status']) != 'ok':
        status = '500 Internal Server Error'

    # Respond
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
i = 0
for arg in sys.argv:
    if str(arg) == '-f':
        ConfFile = sys.argv[i+1]
    if str(arg) == '-p':
        PidFile = sys.argv[i+1]
    if str(arg) == '-l':
        ListenPort = sys.argv[i+1]
    i += 1

# Run as a daemon....detach and write out the pid file
daemon.daemonize(PidFile)
httpd = make_server('localhost', int(ListenPort), application)
httpd.serve_forever()


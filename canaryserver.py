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

__VERSION__ = "0.8"

## StatusChecker
#
# see README.md
#
class StatusChecker:


    # Class variables
    checksToRun = []
    errorState = False
    lastError = ''
    pidFile = '/tmp/canaryserver.pid'
    confFile = '/etc/canaryserver.cfg'
    listenPort = 8002
    listenHost = 'localhost'
    showTime = False
    showUptime = False
    gracePeriod = 0
    slackToken = None
    slackChannel = None
    alertWindow = 0
    lastErrorFound = 0
    
    ## constructor
    #
    def __init__(self):
        pass

    # Public methods
    
    ## notify
    #
    # Send a message about something
    #
    def notify(self):

        # Check for Slack
        if self.slackToken and self.slackChannel:
            sc = SlackClient(self.slackToken)
            print sc.api_call("chat.postMessage", channel='#' + str(self.slackChannel), username='canary', icon_emoji=':hatched_chick:',
                text="Oh Noes! Something bad happened! Commencing self-desctruct sequence in 5...4...3...")

    ## main call
    #
    # @return status A Dictionary
    # {
    #   status:     'ok|error',
    #   issues:     [ list of error messages ]
    # }
    def checkServerHealth(self):

        # Check for internal errors
        if self.errorState:
            returnStatus = {}
            returnStatus['status'] = 'error'
            returnStatus['issues'] = [self.lastError]
            return returnStatus

        # List of issues
        serverIssues = []

        # Overall status
        serverOverallStatus = 'ok'

        # Do stuff
        for check in self.checksToRun:

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

        # Put time in return if it was asked for
        if str(self.showTime) == 'yes':
            dt = datetime.datetime.now()
            now = str(dt) + " TZ:" + str(dt.tzname())
            returnStatus['datetime'] = now

        # Get uptime.  Put in return if asked for
        systemUptime = uptime()
        if str(self.showUptime) == 'yes':
            returnStatus['uptime'] = str(datetime.timedelta(seconds=systemUptime))

        # Set the status based upon error status
        status = '200 OK'
        if serverOverallStatus != 'ok':
            status = '500 Internal Server Error'

            # See if we are in a "grace period"
            # If we are, always return 200
            if int(self.gracePeriod) > 0 and systemUptime <= float(self.gracePeriod):
                status = '200 OK'
                returnStatus['inGracePeriod'] = 'true'

            # otherwise, see if we are in error window to send out notify
            elif (systemUptime - self.lastErrorFound) > float(self.alertWindow):

                # The time since we last reported an error is more than our alert window,
                # so  send out a notify
                self.lastErrorFound = systemUptime
                self.notify()

        return status,returnStatus
    
    ## configure
    #
    def configure(self, inputFile):
        myConfParser = ConfigParser.ConfigParser()

        try:
            myConfParser.read(inputFile)

            # Read the healthcheck items out of the conf file
            for item in myConfParser.items('healthchecks'):
                command = item[0]
                arg = item[1]

                # Check and see if item is a list
                for subarg in str(arg).split(','):
                    self.checksToRun.append( [command,subarg] )

            # Read the main items out of the conf file
            for item in myConfParser.items('main'):
                command = item[0]
                arg = item[1]

                if str(command) == 'pidfile':
                    self.pidFile = str(arg)
                elif str(command) == 'listenport':
                    self.listenPort = str(arg)
                elif str(command) == 'listenhost':
                    self.listenHost = str(arg)
                elif str(command) == 'showtime':
                    self.showTime = str(arg)
                elif str(command) == 'showuptime':
                    self.showUptime = str(arg)
                elif str(command) == 'graceperiod':
                    self.gracePeriod = str(arg)
                elif str(command) == 'alertwindow':
                    self.alertWindow = str(arg)

            # Read the notify items out of the conf file
            for item in myConfParser.items('notify'):
                command = item[0]
                arg = item[1]
                if str(command) == 'slacktoken':
                    self.slackToken = str(arg)
                elif str(command) == 'slackchannel':
                    self.slackChannel = str(arg)

        except Exception as e:
            self.errorState = True
            self.lastError = 'Canary could not fly (loading conf file ' + str(inputFile) + ': ' + str(e)

    ## Private methods

    ## checkPS
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

    ## checkPort
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

    ## ip4_addresses
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


    ## checkPidfile
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

    # Check server health
    serverStatus = {}
    status = None

    # Make the server status check call
    # Wrap in try/catch
    try:
        status,serverStatus = SC.checkServerHealth()
    except Exception as e:
        serverStatus['status'] = 'error'
        serverStatus['issues'] = ['Couldn\'t check server health: ' + str(e)]
        status = '500 Internal Server Error'

    # Respond
    response_body = str(serverStatus)
    response_headers = [('Content-Type', 'text/plain'),
                        ('Content-Length', str(len(response_body)))]
    start_response(status, response_headers)
    return [response_body]

## "main"

# Create our StatusChecker
SC = StatusChecker()

# Check command line args
ConfFile = '/etc/canaryserver.cfg'
i = 0
for arg in sys.argv:
    if str(arg) == '-f':
        ConfFile = sys.argv[i+1]
    i += 1

# Configre
SC.configure(ConfFile)

# Run as a daemon....detach and write out the pid file
daemon.daemonize(SC.pidFile)
httpd = make_server(SC.listenHost, int(SC.listenPort), application)
httpd.serve_forever()


import sys
import time
import ssl
import getpass
import socket
import struct
import logging
import argparse
import shlex
import matplotlib.pyplot as plt
import numpy as np
from cmd import Cmd
from poll_message_api import *

#
# Implements client for poll project
#

POLLSERVER_HOST_PORT = ('127.0.0.1', 10000)

POLL_CLIENT_PROMPT = "(poll) "

VERBOSE = 7
TRACE = 4

allCommands = {
   "create_user": "Create new user ID",
   "change_user": "Change existing user ID data",
   "login_user": "Login in to the poll system using a specific user ID",
   "logout_user": "Logout from poll system",
   "create_poll": "Create a new poll",
   "add_poll_choices": "Add new poll choices to existing poll",
   "remove_poll_choices": "Remove poll choices from existing poll",
   "set_poll_status": "Open or Close existing poll",
   "make_poll_choice": "Make poll choice by user",
   "get_poll_results": "Print results for a poll",
   "list_users": "Print list of users in the system",
   "list_polls": "Print list of polls in the system",
   "print_poll": "Print poll data for a given poll",
   "print_user": "Print user data for a given user",
   "quit": "Exit the program",
}

c_sock = None
ssl_c_sock = None
ssl_context = None
use_ssl = True

def CheckServerCertificate(ssl_c_sock):
   if use_ssl:
      ssl_server_cert = ssl_c_sock.getpeercert();
      if not ssl_server_cert:
          raise Exception("Unable to retrieve server certificate");
      else:
         # Validate whether the Certificate is indeed issued to the server
         subject         = dict(item[0] for item in ssl_server_cert['subject']);
         commonName      = subject['commonName'];

         if commonName != 'pesuacademy.server.com':
            raise Exception("Incorrect common name in server certificate");

         notAfterTimestamp   = ssl.cert_time_to_seconds(ssl_server_cert['notAfter']);
         notBeforeTimestamp  = ssl.cert_time_to_seconds(ssl_server_cert['notBefore']);
         currentTimeStamp    = time.time();

         if currentTimeStamp > notAfterTimestamp:
             raise Exception("Expired server certificate");

         if currentTimeStamp < notBeforeTimestamp:
             raise Exception("Server certificate not yet active");
   return

def getSocket():
   global c_sock
   global ssl_c_sock
   global ssl_context

   if c_sock is None:
      c_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

      if use_ssl:
         ssl_context                     = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
         ssl_context.verify_mode         = ssl.CERT_REQUIRED;
         ssl_context.check_hostname      = False
         ssl_context.load_verify_locations("certificates/ca-cert.pem")
         ssl_context.load_cert_chain(certfile="certificates/client-cert.pem", keyfile="certificates/client-key.pem")
         #ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
         ssl_c_sock  = ssl_context.wrap_socket(c_sock)
      else:
         ssl_c_sock = c_sock

      ssl_c_sock.connect(POLLSERVER_HOST_PORT)

      CheckServerCertificate(ssl_c_sock)

   return ssl_c_sock
   
def setupLogging(logLevel, logFile=None, logDir=None):
    """
    Create Logging Infrastructure to be used by various applications

    Adds two custom log levels VERBOSE and TRACE below DEBUG

    :param logLevel: logLevel to be setup for console
    :param logFile: file name for the log file
    :param logDir: directory for log files
    """

    fileLoggingFormat =\
        "%(asctime)s:%(name)s:%(funcName)s:%(lineno)d:%(message)s"
    consoleLoggingFormat = '%(message)s'

    # Add custom log levels
    logging.addLevelName(VERBOSE, 'VERBOSE')
    logging.addLevelName(TRACE, 'TRACE')

    def verbose(self, message, *args, **kws):
        self.log(VERBOSE, message, *args, **kws)

    def trace(self, message, *args, **kws):
        self.log(TRACE, message, *args, **kws)

    logging.Logger.verbose = verbose
    logging.Logger.trace = trace

    logger = logging.getLogger()
    logger.setLevel(TRACE)

    # Create a file handler if specified
    if logDir and logFile is not None:
        fh = logging.FileHandler(logFile + logDir, mode='w')
        fh.setLevel(TRACE)
        fh.setFormatter(logging.Formatter(fileLoggingFormat))
        logger.addHandler(fh)

    # Create Console handler for lesser log messages
    ch = logging.StreamHandler()
    ch.setLevel(logLevel)
    ch.setFormatter(logging.Formatter(consoleLoggingFormat))
    logger.addHandler(ch)

setupLogging(logging.DEBUG)
log = logging.getLogger(__name__)

#
# This class, Shell, is inherited from "Cmd" class
#
# Cmd class is standard class that provides 'shell' like interface. i.e command-line interface with a prompt
#
# For every line entered, the Cmd (parent class) call onecmd() method with the user entered line.
# onecmd() method can parse the user input line and take action.
#
# In this Shell implementation, every "command" implementation is implemented as do_<command> function.
#
# The function gets called with list of strings derived from user input line split into seperate strings.
# These are arguments to the "command itself.
#
# Each of these "do_<command>" method implements the communication with server and back for the specific operation.
#
# For ex: "create_user" command method, do_create_user(), gets list as argument containing [userId, userName, userEmail, password] 
#          do_create_user() method, then calls the message transport API, sendCreateUserReqMsg() to send
#          the "create_user" request to server using the socket. Then it waits for response from server using
#          transport API recvResponseMessage().
#
# Multiple comments added in the starting of each command implementation is used as help for the corresponding command.
#
# "help" at command prompt will list all the supported commands. This is from "allCommands" dictionary.
#
# All the commands with arguments can be put in a text file and file name can be supplied as argument
# to the script to do batch processing of the commands.
#

class Shell(Cmd):
    """
    Generic shell commands for binedit
    """

    def __init__(self, input=None):
        if input:
           self.use_rawinput = False
           Shell.use_rawinput = False
           self.prompt = ''
        else:
           self.use_rawinput = True
           self.prompt = POLL_CLIENT_PROMPT

        Cmd.__init__(self, stdin=input)

        if self.use_rawinput:
           self.do_help(None)

    def default(self, line):
        log.info('No such command: {}'.format(line))

    def onecmd(self, line):
        """
        Override the base class to take care of argparse adjustments

        :param line: typed in by user in shell

        """
        cmd, arg, line = self.parseline(line)
        if not line:
            return self.emptyline()
        if line[0] == '#':
           return None
        if cmd is None:
            return self.default(line)
        self.lastcmd = line
        if line == 'EOF':
            cmd = 'quit'
        if cmd == '':
            return self.default(line)
        else:
            try:
                # look for function with "do_<command>" in the class object
                func = getattr(self, 'do_' + cmd)
            except AttributeError:
                return self.default(line)

            try:
               args = shlex.split(arg)
               print("Command :", cmd, args)
               return func(args)
            except ValueError as ex:
               print(ex)
               pass

            return None

    def do_help(self, args):
        'List available commands with "help" or detailed help with "help cmd".'
        if args:
           helpCmd = args[0]
           try:
              doc = getattr(self, 'do_' + helpCmd).__doc__
              if doc:
                 self.stdout.write("%s\n" % str(doc))
                 return
           except AttributeError:
              self.stdout.write("No help available for %s\n" % (helpCmd))
              pass
        else:
           print("Enter any of following commands")
           for c in allCommands:
              print("\t%s : %s" %(c, allCommands[c]))

    @staticmethod
    def do_quit(args):
        """ usage: quit
        Quit the shell
        """
        return True

    def do_create_user(self, args):
        """ usage: create_user userID userName userEmail [password]
        Create a new user ID.

        The command will prompt for password if not given.
        """

        if len(args) < 3:
           print('Not enough arguments given. Type help <command>')
           return

        if len(args) == 3:
           password = getpass.getpass()
        else:
           password = args[3]

        sock = getSocket()
        r = sendCreateUserReqMsg(sock, args[0], args[1], args[2], password)
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_change_user(self, args):
        """ usage: change_user userName userEmail [password]
        Change exiting user data.

        The change of data must be for an existing already logged user. The command will prompt for password if not given.
        """

        if len(args) < 3:
           print('Not enough arguments given. Type help <command>')
           return

        if len(args) == 3:
           password = getpass.getpass()
        else:
           password = args[3]

        sock = getSocket()
        r = sendChangeUserReqMsg(sock, args[0], args[1], args[2], password)
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_login_user(self, args):
        """ usage: login_user userID [password]
        Logon to poll system

        userID must be for an existing user. The command will prompt for password if not given.
        """

        if len(args) < 1:
           print('Not enough arguments given. Type help <command>')
           return

        if len(args) == 1:
           password = getpass.getpass()
        else:
           password = args[3]

        sock = getSocket()
        r = sendLoginUserReqMsg(sock, args[0], password)
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_logout_user(self, args):
        """ usage: logout_user
        Logout from poll system

        userID must be for an existing loggedin user.
        """
        sock = getSocket()
        r = sendLogoutUserReqMsg(sock)
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_create_poll(self, args):
        """ usage: create_poll pollID pollName openDateTime closeDateTime [choiceID,choiceName, ...]
        Create a new poll in the system
        """

        if len(args) < 4:
           print('Not enough arguments given. Type help <command>')
           return

        sock = getSocket()
        if len(args) > 4:
           it = iter(args[4:])
           pollChoices = [*zip(it, it)]
        else:
           pollChoices = []
        r = sendCreatePollReqMsg(sock, args[0], args[1], args[2], args[3], pollChoices)
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_add_poll_choices(self, args):
        """ usage: add_poll_choices pollID choiceID choiceName ...
        Add new choices to existing poll
        """

        if len(args) < 3:
           print('Not enough arguments given. Type help <command>')
           return

        sock = getSocket()
        it = iter(args[1:])
        pollChoices = [*zip(it, it)]
        r = sendAddPollChoicesReqMsg(sock, args[0], pollChoices)
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_remove_poll_choices(self, args):
        """ usage: remove_poll_choices pollID choiceID  ...
        Remove choices from existing poll
        """

        if len(args) < 2:
           print('Not enough arguments given. Type help <command>')
           return

        sock = getSocket()
        r = sendRemovePollChoicesReqMsg(sock, args[0], args[1:])
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_set_poll_status(self, args):
        """ usage: set_poll_status pollID poll-status
        Change the status of the existing poll to open or close
        """

        if len(args) < 2:
           print('Not enough arguments given. Type help <command>')
           return

        sock = getSocket()
        r = sendSetPollStatusDataReq(sock, args[0], args[1])
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

    def do_list_users(self, args):
        """ usage: list_users
        List the users in the system
        """

        sock = getSocket()
        r = sendListUsersReq(sock)
        msgType, flags, status, reason, usersData = recvListUsersResponse(sock)
        if status is not None:
           print(GetMsgTypeString(msgType), "finished with status", GetReasonString(reason))
           if status == 0:
              for i in usersData:
                 print('\tuserID: %s, userName: %s, userEmail: %s' %(i['userID'], i['userName'], i['userEmail']))

    def do_list_polls(self, args):
        """ usage: list_polls
        List the polls created by the currently logged in user in the system
        """

        sock = getSocket()
        r = sendListPollsReq(sock)
        msgType, flags, status, reason, pollList = recvListPollsResponse(sock)
        if status is not None:
           print(GetMsgTypeString(msgType), "finished with status", GetReasonString(reason))
           if status == 0:
              for i in pollList:
                 print('\tpollID: %s, pollName: %s, pollStatus: %s' %(i['pollID'], i['pollName'], i['pollStatus']))
                 for j in i['choices']:
                    print('\t\tchoiceID: %s, choiceName: %s, pollCount: %s' %(j['choiceID'], i['choiceName'], i['pollCount']))

    def do_get_poll_results(self, args):
        """ usage: get_poll_results pollID
        Print the ressults for a given pollID
        """

        sock = getSocket()

        if len(args) < 1:
           print('Not enough arguments given. Type help <command>')
           return

        r = sendPollGetResultsReq(sock, args[0])
        msgType, flags, status, reason, (pollName, pollResults) = recvPollGetResultsResponse(sock)
        if status is not None:
           print(GetMsgTypeString(msgType), "finished with status", GetReasonString(reason))
           if status == 0:
              print("\tpollName: %s" %(pollName))
              for i in pollResults:
                 print('\t\tchoicename: %s, count: %s' %(i['choiceName'], i['count']))

        if len(pollResults) > 0 and len(args) > 1 and args[1] == 'pie':
           values = [i['count'] for i in pollResults]
           vlabels =  [i['choiceName'] for i in pollResults]
           y = np.array(values)
           plt.pie(values, labels=vlabels, autopct='%1.1f%%')
           plt.legend(title = pollName)
           plt.show()

    def do_make_poll_choice(self, args):
        """ usage: make_poll_choice pollID choiceID
        Make choice selection for a poll. User must be logged in.
        """

        if len(args) < 2:
           print('Not enough arguments given. Type help <command>')
           return

        sock = getSocket()
        r = sendPollMakeSelectionReq(sock, args[0], args[1])
        msgType, flags, status, reason = recvResponseMessage(sock)
        print(GetMsgTypeString(msgType), args, status, GetReasonString(reason))

if __name__ == '__main__':
   plt.set_loglevel (level = 'warning')
   if len(sys.argv) > 1:
      input = open(sys.argv[1], 'rt')
      try:
         Shell(input=input).cmdloop()
      finally:
         input.close()
   else:
      Shell().cmdloop()

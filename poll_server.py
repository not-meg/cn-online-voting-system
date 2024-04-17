import sys
import time
import ssl
import socket
import threading
import poll_useropsimpl
import poll_pollopsimpl
import poll_invalidmsgimpl
import poll_dbopsimpl
from poll_message_api import *

POLLSERVER_HOST_PORT = ('127.0.0.1', 10000)
POLLSERVER_NUM_WAIT_REQS = 25

# Following dict maps incoming socket request to the processing class
#
# When a message is received via socket, server reads the first 8-bytes of the
# message. This gives the type of message. The type of the message will be one
# of the items in the following dict. The actual processing for that message
# is implemented in the corresponding class
#
msgType2CBMap = {
   # Request type             # Processing class
   CREATE_USER              : poll_useropsimpl.CreateUserImpl,
   CHANGE_USER              : poll_useropsimpl.ChangeUserImpl,
   LOGIN_USER               : poll_useropsimpl.LoginUserImpl,
   LOGOUT_USER              : poll_useropsimpl.LogoutUserImpl,
   LIST_USERS               : poll_useropsimpl.ListUsersImpl,
   CREATE_POLL              : poll_pollopsimpl.CreatePollImpl,
   POLL_ADD_CHOICES         : poll_pollopsimpl.AddPollChoicesImpl,
   POLL_REMOVE_CHOICES      : poll_pollopsimpl.RemovePollChoicesImpl,
   POLL_SET_STATUS          : poll_pollopsimpl.SetPollStatusImpl,
   USER_POLL_MAKE_SELECTION : poll_pollopsimpl.PollMakeSelectionImpl,
   USER_POLL_GET_RESULTS    : poll_pollopsimpl.PollGetResultsImpl,
   LIST_POLLS               : poll_pollopsimpl.ListPollsImpl,
}

# Validates the client SSL certificate 
def CheckClientCertificate(ssl_cl_sock):
   # use of ssl can be disabled if desired by setting use_ssl = False
   if not use_ssl:
      return

   # Get certificate from the client
   ssl_client_cert = ssl_cl_sock.getpeercert();

   # Check the client certificate bears the expected name as per server's policy
   if not ssl_client_cert:
      raise Exception("Unable to get the certificate from the client");
   else:
      clt_subject    = dict(item[0] for item in ssl_client_cert['subject']);
      clt_commonName = clt_subject['commonName'];

      if clt_commonName != 'pesuacademy.client.com':
         raise Exception("Incorrect common name in client certificate");

      # Check time validity of the client certificate
      t1  = ssl.cert_time_to_seconds(ssl_client_cert['notBefore']);
      t2  = ssl.cert_time_to_seconds(ssl_client_cert['notAfter']);
      ts  = time.time();

      if ts < t1:
         raise Exception("Client certificate not yet active");

      if ts > t2:
         raise Exception("Expired client certificate");

#
# This is the main function for the thread that processes the client request
#
# The server creates a thread for every client socket connection. The thread remains
# for entire time of client connection. i.e all the client request will be processed
# inside the newly created thread
#
def ThreadMain(cl_sock):
   print(cl_sock)

   #
   # Before starting the thread, the server stashes certain useful info
   # in a dict indexed by the socket object. This is called thread-context.
   # The newly created thread fetches that context info which in turn
   # contains database connection, lock, logged in info and few other details
   #
   cntxt = poll_dbopsimpl.GetThreadContext(cl_sock)
   conn = cntxt['conn']
   lock = cntxt['lock']
   print(cntxt)

   # The thread runs until the socket is closed
   while True:
      # read the message header which is 8-bytes
      msgBuf = cl_sock.recv(ctypes.sizeof(PollMsgHdr))

      # If client closed the socket, recv returns None, exit the thread
      if not msgBuf:
         break

      #
      # The msgBuf is in sequence of bonary bytes. Typecase it to a C-style
      # struct so we can examine the contents
      #
      msgHdr = PollMsgHdr.from_buffer(bytearray(msgBuf))

      # convert from network-byte-order to host-byte-order
      msgType = socket.ntohs(msgHdr.msgType)
      msgFlags = socket.ntohs(msgHdr.flags)

      print(msgType, msgFlags)
      # check if the message type in the request is supported
      if msgType in msgType2CBMap:
         #
         # if supported, create the instance of the corresponding class
         # and call the invoke() method of the class.
         #
         # invoke() method actually does the rest of the processing
         # for the request.
         #
         # Every class is designed such that is:
         #     has constructor which stashes the useful params in the object instance
         #     has invoke() method that processes the request
         #
         # Every request has a different format. Only common stuff is 
         # PollMsgHdr. The rest is dependent on the message type, hence
         # the thread only reads the PollMsgHdr from socket and leaves the
         # rest of the request data to be read and interpreted by the
         # corresponding invoke() method
         #
         # A return value of True from invoke() method indicates something is wrong
         # with the request and connection must be terminated.
         #
         if msgType2CBMap[msgType](cl_sock, cntxt, conn).invoke():
            break
      else:
         # if the message type is not supported, call common handling function
         poll_invalidmsgimpl.InvalidMsgReqImpl(cl_sock, cntxt, conn).invoke()
         break

   # Before closing the socket and exiting the thread clean up the thread
   # context
   poll_dbopsimpl.RemoveThreadContext(cl_sock)

   # close the socket
   cl_sock.close()

# start a new thread for serviving the client socket
def start_new_thread(cl_sock, cl_address, conn, lock):
   # creates the thread
   ct = threading.Thread(target=ThreadMain, args=(cl_sock,))
   if ct:
      # if the thread creation is successful, save the important
      # info so that the new thread can access them
      poll_dbopsimpl.AddThreadContext(cl_sock, cl_address, conn, lock)

      # start the thread -- invokes ThreadMain() function
      ct.start()

# connect to database
conn = poll_dbopsimpl.ConnectDatabase()
if not conn:
   sys.exit(1)

# create tables if needed
cur = poll_dbopsimpl.CreateTables(conn)
if not cur:
   sys.exit(1)

use_ssl = True

# create a common lock to synchronize access to the database tables
lock = threading.Lock()

# create server socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# setup SSL context
ssl_context                     = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_context.verify_mode         = ssl.CERT_REQUIRED;

# CA certificate
ssl_context.load_verify_locations("certificates/ca-cert.pem")

# server certificate and server key
ssl_context.load_cert_chain(certfile="certificates/server-cert.pem", keyfile="certificates/server-key.pem")

if use_ssl:
   # if SSL is enabled, wrap the normal socket with SSL so all send and recv's go via SSL channel
   ssl_sock = ssl_context.wrap_socket(sock, server_side=True)
else:
   ssl_sock = sock

ssl_sock.bind(POLLSERVER_HOST_PORT)
ssl_sock.listen(POLLSERVER_NUM_WAIT_REQS)

while True:
   # wait for connection from client
   (ssl_cl_sock, cl_address) = ssl_sock.accept()

   # validate the client's certificate
   CheckClientCertificate(ssl_cl_sock)

   # create new thread for the client
   start_new_thread(ssl_cl_sock, cl_address, conn, lock)

sock.close()
ssl_socket.close()

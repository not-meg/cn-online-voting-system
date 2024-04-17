import sys
import threading
from poll_message_api import *
import poll_dbopsimpl

# Server side message handling implementations
#
# Each poll operation is implemented as seperate class
#
# Each class should have :
#  a construcctor which takes 3 arguments:
#     cl_sock: connected client socket object
#     cl_cntxt : The socket context object for the thread
#     conn: The database connect object
#
#  a invoke() method:
#     invoke() method is called with no-arguments on the object that is instantiated.
#     So, the constructor must save the arguments passed in the object instance so that they
#     can be accessed by the invoke() method.
#
#     The invoke() method is responsible for reading the rest of the data from the client's request
#     validating and processing and responding to the request.
#
#     More methods can be implemented as needed, more variables may be added to the instance as needed.
#

class CreatePollImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.userID = self.cntxt['userID']
      self.op = CREATE_POLL

   def invoke(self):
      print("ENTER CreatePollImpl", self.cntxt)
      pollID, pollName, openDateTime, closeDateTime, pollChoices = recvCreatePollData(self.sock)
      print(pollID, pollName, openDateTime, closeDateTime, pollChoices)

      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         status, reason = OP_FAILURE, REASON_NOT_LOGGED_IN
      else:
         ### LOCK POLL TABLE
         self.lock.acquire()
         status, reason = poll_dbopsimpl.AddPoll(self.conn, self.userID, pollID, pollName, openDateTime, closeDateTime, pollChoices)
         ### UNLOCK POLL TABLE
         self.lock.release()

      r = sendResponseMessage(self.sock, self.op, status, reason)
      print(r)
      print("EXIT CreatePollImpl", self.cntxt)
      return 0

class AddPollChoicesImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = POLL_ADD_CHOICES
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER AddPollChoicesImpl", self.cntxt)
      pollID, pollChoices = recvAddPollChoicesData(self.sock)
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         status, reason = OP_FAILURE, REASON_NOT_LOGGED_IN
      else:
         ### LOCK POLL TABLE
         self.lock.acquire()
         status, reason = poll_dbopsimpl.AddPollChoices(self.conn, pollID, self.userID, pollChoices)
         ### UNLOCK POLL TABLE
         self.lock.release()

      r = sendResponseMessage(self.sock, self.op, status, reason)
      print(r)
      print("EXIT AddPollChoicesImpl", self.cntxt)
      return 0

class RemovePollChoicesImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = POLL_REMOVE_CHOICES
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER RemovePollChoicesImpl", self.cntxt)
      pollID, pollChoices = recvRemovePollChoicesData(self.sock)
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         status, reason = OP_FAILURE, REASON_NOT_LOGGED_IN
      else:
         ### LOCK POLL TABLE
         self.lock.acquire()
         status, reason = poll_dbopsimpl.RemovePollChoices(self.conn, pollID, self.userID, pollChoices)
         ### UNLOCK POLL TABLE
         self.lock.release()

      r = sendResponseMessage(self.sock, self.op, status, reason)
      print(r)
      print("EXIT RemovePollChoicesImpl", self.cntxt)
      return 0

class SetPollStatusImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = POLL_SET_STATUS
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER SetPollStatusImpl", self.cntxt)
      pollID, pollStatus = recvSetPollStatusData(self.sock)
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         status, reason = OP_FAILURE, REASON_NOT_LOGGED_IN
      else:
         ### LOCK POLL TABLE
         self.lock.acquire()
         status, reason = poll_dbopsimpl.SetPollStatus(self.conn, pollID, self.userID, pollStatus)
         ### UNLOCK POLL TABLE
         self.lock.release()

      r = sendResponseMessage(self.sock, self.op, status, reason)
      print(r)
      print("EXIT SetPollStatusImpl", self.cntxt)
      return 0

class PollMakeSelectionImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = USER_POLL_MAKE_SELECTION
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER PollMakeSelectionImpl", self.cntxt)
      pollID, choiceID = recvPollMakeSelectionReqData(self.sock)
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         status, reason = OP_FAILURE, REASON_NOT_LOGGED_IN
      else:
         ### LOCK POLL TABLE
         self.lock.acquire()
         status, reason = poll_dbopsimpl.PollMakeSelection(self.conn, pollID, self.userID, choiceID)
         ### UNLOCK POLL TABLE
         self.lock.release()

      r = sendResponseMessage(self.sock, self.op, status, reason)
      print(r)
      print("EXIT PollMakeSelectionImpl", self.cntxt)
      return 0

class PollGetResultsImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = USER_POLL_GET_RESULTS
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER PollGetResultsImpl", self.cntxt)
      pollID = recvPollGetResultsReqData(self.sock)
      if pollID is None:
         return OP_FAILURE
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         status, reason, pollResults = OP_FAILURE, REASON_NOT_LOGGED_IN, []
      else:
         ### LOCK POLL TABLE
         self.lock.acquire()
         status, reason, pollName, pollResults = poll_dbopsimpl.PollGetResults(self.conn, pollID)
         ### UNLOCK POLL TABLE
         self.lock.release()

      print(status, reason, pollName, pollResults)
      r = sendPollGetResultsResponse(self.sock, status, reason, pollName, pollResults)
      print("EXIT PollGetResultsImpl", self.cntxt)
      return OP_SUCCESS

class ListPollsImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = LIST_POLLS
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER ListPollsImpl", self.cntxt)
      pollID = recvListPollsReqData(self.sock)
      if pollID is None:
         return OP_FAILURE

      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         res, reason, pollList = OP_FAILURE, REASON_NOT_LOGGED_IN, []
      else:
         ### LOCK USER TABLE
         self.lock.acquire()
         res, reason, pollList = poll_dbopsimpl.ListPolls(self.cntxt, pollID)
         ### UNLOCK USER TABLE
         self.lock.release()

      r = sendListPollsResponse(self.sock, res, reason, pollList)
      print(r)
      print("EXIT ListPollsImpl", self.cntxt)
      return OP_SUCCESS

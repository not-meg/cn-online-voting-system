import sys
from poll_message_api import *
import poll_dbopsimpl

#
# Implements user operations
#
# Each user operation is implemented as seperate class
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

# Server side message handling implementations
class CreateUserImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn

   def invoke(self):
      print("ENTER CreateUserImpl", self.cntxt)

      # Read the rest of the data from socket
      userID, userName, userEmail, userPwd = recvCreateUserData(self.sock)
      print(userID, userName, userEmail, userPwd)

      # Validate the input data -- yet to be done

      ### LOCK USER TABLE
      self.lock.acquire()

      # Add the user details in to the database
      # 'res' is either OP_SUCCESS or OP_FAILURE
      # 'reason' indicates the actual FAILURE code inf case of FAILURE (see REASON_*)
      res, reason = poll_dbopsimpl.AddUser(self.conn, userID, userName, userEmail, userPwd)

      ### UNLOCK USER TABLE
      self.lock.release()

      # send the response -- for create-user request, the response is just success or failure
      r = sendResponseMessage(self.sock, CREATE_USER, res, reason)
      print(r)
      print("EXIT CreateUserImpl", self.cntxt)
      return 0

class ChangeUserImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = CHANGE_USER
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER ChangeUserImpl", self.cntxt)
      userID, userName, userEmail, userPwd = recvChangeUserData(self.sock)
      if not (userID == self.userID and poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt)):
         res = OP_FAILURE
         reason = REASON_NOT_LOGGED_IN
      else:
         print(self.userID, userName, userEmail, userPwd)

         ### LOCK USER TABLE
         self.lock.acquire()
         res, reason = poll_dbopsimpl.ChangeUser(self.conn, self.userID, userName, userEmail, userPwd)
         ### UNLOCK USER TABLE
         self.lock.release()

      r = sendResponseMessage(self.sock, self.op, res, reason)
      print(r)
      print("EXIT ChangeUserImpl", self.cntxt)
      return 0

class LoginUserImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = LOGIN_USER

   def invoke(self):
      print("ENTER LoginUserImpl", self.cntxt)
      userID, userPwd = recvLoginUserData(self.sock)
      print(userID, userPwd)
      ### LOCK USER TABLE
      self.lock.acquire()

      # check if the user has already loggedn-in
      if poll_dbopsimpl.IsUserLoggedIn(userID):
         res = OP_FAILURE
         reason = REASON_ALREADY_LOGGED_IN
      else:
         # check if the userID is valid one
         res, reason = poll_dbopsimpl.ValidateUser(self.conn, userID, userPwd)
         if res == OP_SUCCESS:
            # Mark that the user has logged-in with the userID in the thread-context object
            res, reason = poll_dbopsimpl.SetUserLoggedIn(userID, self.cntxt)
      ### UNLOCK USER TABLE
      self.lock.release()

      # send the response OP_SUCCESS or OP_FAILURE with reason code
      r = sendResponseMessage(self.sock, self.op, res, reason)
      print(r)
      print("EXIT LoginUserImpl", self.cntxt)
      return 0

class LogoutUserImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = LOGOUT_USER
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER LogoutUserImpl", self.cntxt)
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         res, reason = OP_FAILURE, REASON_NOT_LOGGED_IN
      else:
         ### LOCK USER TABLE
         self.lock.acquire()
         poll_dbopsimpl.SetUserLoggedOut(self.cntxt)
         ### UNLOCK USER TABLE
         self.lock.release()
         res, reason = OP_SUCCESS, REASON_SUCCESS

      r = sendResponseMessage(self.sock, self.op, res, reason)
      print("EXIT LogoutUserImpl", self.cntxt)
      return

class ListUsersImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.lock = self.cntxt['lock']
      self.conn = conn
      self.op = LIST_USERS
      self.userID = self.cntxt['userID']

   def invoke(self):
      print("ENTER ListUsersImpl", self.cntxt)

      # only logged-in users can get the list of users
      if not poll_dbopsimpl.AmILoggedIn(self.userID, self.cntxt):
         res, reason, userList = OP_FAILURE, REASON_NOT_LOGGED_IN, []
      else:
         ### LOCK USER TABLE
         self.lock.acquire()
         res, reason, userList = poll_dbopsimpl.ListUsers(self.cntxt)
         ### UNLOCK USER TABLE
         self.lock.release()

      # the response contains whether the op is success and if yes, will also contain list of user and data
      r = sendListUsersResponse(self.sock, res, reason, userList)
      print(r)
      print("EXIT ListUsersImpl", self.cntxt)
      return 0

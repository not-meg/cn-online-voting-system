import sys
import socket
import struct
import ctypes
import hashlib

#
# Implements transport API's sending, receiving request and responses between client and server via socket
#
# General usage:
#
# For sending and receiving messages, C-style struct is defined with required members with required size
#
# When a client sends certain request, the server need to know the format of that request so that it knows
# how to interpret the data and the same goes when server sends any message to the client as well.
#
# Using the C-style struct helps to exchange the requests and responses between client and server with
# fixed size (on per request basis)
#
# Each message is divided into atleast 2 parts:
#   'hdr' which is of type PollMsgHdr
#   'data' varies by the request
#
# 'hdr' of type PollMsgHdr indicates what is the request type. Knowing the request type, the server will be able
# to interpret the rest of the data in the request appropriately. A given request-type will always carry same
# type of information. For ex: create_user will always carry, userID, userName, e-mail, password and all these
# fields will be of fixed size. So, knowing the request-type, the server will know how much more bytes to read
# from the socket and how to interpret those bytes (i.e how many bytes are userID, how many bytes are userName
# etc)
#
# In some cases, the data in the request/response can be varied length. i.e it can be array of data. In that case
# following the 'hdr', there will be a field indicating number of elements in the ldata part of the request/response.
# For ex: list_users response, add_poll_choices request
#
# When sending and reciving data via socket, all numeric fields have to be properly converted. i.e while sending
# the numeric values have to be converted to network-byte-order and while receiving, the numerics have to be converted
# from network-byte-order to host-byte-order. This is done by using htons() and htons() for uint16.
#
# Since C-style struct is used to send and recv the requests, the unused parts of the fields in the structs are
# filled with binary 0's. The receiver must trim those bytes before using those fields as those are not valid data.
#
# Each C-style struct as following:
#   _fields_ = [('fieldName', size), ...] : Array of field tuple with thier size
#   _pack_ = 1 : indicates not to do any alignment or padding.
#
# All send* functions return O_SUCCESS or OP_FAILURE as the return value
# All recv* functions return tuple of data items received from the socket, type of None of failure
#

# Status codes
OP_SUCCESS = 0
OP_FAILURE = 1

# Reason codes
REASON_SUCCESS = 0
REASON_NOT_LOGGED_IN = 1
REASON_ALREADY_LOGGED_IN = 2
REASON_INCORRECT_PWD = 3
REASON_DUPLICATE_USER_ID = 4
REASON_USER_ID_NOT_FOUND = 5
REASON_DUP_POLL_DATA = 6
REASON_DATABASE_ERROR = 7
REASON_NOSUCH_POLL_ID = 8
REASON_NOT_ENOUCH_CHOICES = 9
REASON_POLL_NOT_OPENED = 10
REASON_INVALID_POLL_STATUS = 11
REASON_NOT_OWNER = 12
REASON_UNKNOWN = 99

# Reason strings
reason2stringMap = {
   REASON_SUCCESS: "Success.",
   REASON_NOT_LOGGED_IN: "User has not logged-in. Operation requires the user to be logged-in in the current session.",
   REASON_ALREADY_LOGGED_IN: "User already logged-in. Only one login is allowed per user at a time.",
   REASON_INCORRECT_PWD: "Incorrect password. Check the spelling.",
   REASON_DUPLICATE_USER_ID: "User ID already exist. Choose a different one",
   REASON_USER_ID_NOT_FOUND: "Unrecognized User ID. Check the User ID spelling",
   REASON_DUP_POLL_DATA: "Either pollID or pollID + choiceID combination already exists",
   REASON_DATABASE_ERROR: "Internal database error",
   REASON_NOSUCH_POLL_ID: "Given poll does not exist",
   REASON_NOT_ENOUCH_CHOICES: "Atleast 2 poll choices must be given",
   REASON_POLL_NOT_OPENED: "Can not make selection. Poll is closed",
   REASON_INVALID_POLL_STATUS: "Invalid poll status. Should be C or O",
   REASON_NOT_OWNER: "Permission denied. Not the owner",
   REASON_UNKNOWN: "Unknown reason",
}

# Message types
CREATE_USER = 1
CHANGE_USER = 2

LOGIN_USER = 3
LOGOUT_USER = 4

CREATE_POLL = 5
POLL_ADD_CHOICES = 6
POLL_REMOVE_CHOICES = 7
POLL_SET_STATUS = 8

USER_POLL_MAKE_SELECTION = 9
USER_POLL_GET_RESULTS = 10

LIST_USERS = 11
LIST_POLLS = 12

# msg type strings
msgtype2stringMap = {
   CREATE_USER: "Create User Operation",
   CHANGE_USER: "Change User Operation",
   LOGIN_USER: "Login User Operation",
   LOGOUT_USER: "Logout User Operation",
   LIST_USERS: "List Users Operation",
   CREATE_POLL: "Create Poll Operation",
   POLL_ADD_CHOICES: "Add Poll Choices Operation",
   POLL_REMOVE_CHOICES: "Remove Poll Choices Operation",
   POLL_SET_STATUS: "Set Poll Status Operation",
   USER_POLL_MAKE_SELECTION: "Make Poll Section Operation",
   USER_POLL_GET_RESULTS: "Get Poll Results Operation",
   LIST_POLLS: "Get a list of polls",
}

def GetMsgTypeString(msgType):
   if msgType in msgtype2stringMap:
      return msgtype2stringMap[msgType]
   else:
      return 'Unknown'

def GetReasonString(reason):
   if reason in reason2stringMap:
      return reason2stringMap[reason]
   else:
      return 'Unknown'

# Message data

# Create user request
USER_ID_SIZE = 20
POLL_ID_SIZE = 20
CHOICE_ID_SIZE = 20
USER_NAME_SIZE = 30
POLL_NAME_SIZE = 30
CHOICE_NAME_SIZE = 30
USER_EMAIL_SIZE = 30
USER_PWD_SIZE = 15
DATE_TIME_SIZE = 30

def DecodeAndStrip(barr):
   return barr.decode().rstrip('\x00')

class PollMsgHdr(ctypes.Structure):
    _fields_ = [('msgType', ctypes.c_uint16),
                ('flags', ctypes.c_uint16)]
    _pack_ = 1

class PollCreateUserData(ctypes.Structure):
    _fields_ = [('userID', ctypes.c_char * USER_ID_SIZE),
                ('userName', ctypes.c_char * USER_NAME_SIZE),
                ('userEmail', ctypes.c_char * USER_EMAIL_SIZE),
                ('userPwd', ctypes.c_char * USER_PWD_SIZE)]
    _pack_ = 1

class PollCreateUserDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', PollCreateUserData)]
    _pack_ = 1

def sendCreateUserReqMsg(sock, userID, userName, userEmail, userPwd):
   createUserDataReq = PollCreateUserDataReq()
   createUserDataReq.hdr.msgType = socket.htons(CREATE_USER)
   createUserDataReq.hdr.flags = socket.htons(1)
   createUserDataReq.data.userID = userID.encode()
   createUserDataReq.data.userName = userName.encode()
   createUserDataReq.data.userEmail = userEmail.encode()
   createUserDataReq.data.userPwd = userPwd.encode()
   if sock.send(createUserDataReq) == ctypes.sizeof(PollCreateUserDataReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvCreateUserData(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollCreateUserData))
   if  not msgBuf:
      return (None, None, None, None)
   createUserData = PollCreateUserData.from_buffer(bytearray(msgBuf))
   userID = createUserData.userID.decode().rstrip('\x00')
   userName = createUserData.userName.decode().rstrip('\x00')
   userEmail = createUserData.userEmail.decode().rstrip('\x00')
   userPwd = hashlib.sha256(createUserData.userPwd).hexdigest()

   return (userID, userName, userEmail, userPwd)

# Message response
class PollResponseMessage(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('status', ctypes.c_uint16),
                ('reason', ctypes.c_uint16)]
    _pack_ = 1

def sendResponseMessage(sock, msgType, status, reason):
   msgResp = PollResponseMessage()
   msgResp.hdr.msgType = socket.htons(msgType)
   msgResp.hdr.flags = socket.htons(2)
   msgResp.status = socket.htons(status)
   msgResp.reason = socket.htons(reason)
   if sock.send(msgResp) == ctypes.sizeof(PollResponseMessage):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvResponseMessage(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollResponseMessage))
   if  not msgBuf:
      return (None, None, None, None)
   msgResp = PollResponseMessage.from_buffer(bytearray(msgBuf))
   return (socket.ntohs(msgResp.hdr.msgType), socket.ntohs(msgResp.hdr.flags), socket.ntohs(msgResp.status), socket.ntohs(msgResp.reason))

# Poll change user
class PollChangeUserData(ctypes.Structure):
    _fields_ = [('userID', ctypes.c_char * USER_ID_SIZE),
                ('userName', ctypes.c_char * USER_NAME_SIZE),
                ('userEmail', ctypes.c_char * USER_EMAIL_SIZE),
                ('userPwd', ctypes.c_char * USER_PWD_SIZE)]
    _pack_ = 1

class PollChangeUserDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', PollChangeUserData)]
    _pack_ = 1

def sendChangeUserReqMsg(sock, userID, userName, userEmail, userPwd):
   changeUserDataReq = PollChangeUserDataReq()
   changeUserDataReq.hdr.msgType = socket.htons(CHANGE_USER)
   changeUserDataReq.hdr.flags = socket.htons(1)
   changeUserDataReq.data.userID = userID.encode()
   changeUserDataReq.data.userName = userName.encode()
   changeUserDataReq.data.userEmail = userEmail.encode()
   changeUserDataReq.data.userPwd = userPwd.encode()
   if sock.send(changeUserDataReq) == ctypes.sizeof(PollChangeUserDataReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvChangeUserData(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollChangeUserData))
   if  not msgBuf:
      return (None, None, None)
   changeUserData = PollChangeUserData.from_buffer(bytearray(msgBuf))
   userID = changeUserData.userID.decode().rstrip('\x00')
   userName = changeUserData.userName.decode().rstrip('\x00')
   userEmail = changeUserData.userEmail.decode().rstrip('\x00')
   userPwd = hashlib.sha256(changeUserData.userPwd).hexdigest()

   return (userID, userName, userEmail, userPwd)

# Poll login user
class PollLoginUserData(ctypes.Structure):
    _fields_ = [('userID', ctypes.c_char * USER_ID_SIZE),
                ('userPwd', ctypes.c_char * USER_PWD_SIZE)]
    _pack_ = 1

class PollLoginUserDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', PollLoginUserData)]
    _pack_ = 1

def sendLoginUserReqMsg(sock, userID, userPwd):
   loginUserDataReq = PollLoginUserDataReq()
   loginUserDataReq.hdr.msgType = socket.htons(LOGIN_USER)
   loginUserDataReq.hdr.flags = socket.htons(1)
   loginUserDataReq.data.userID = userID.encode()
   loginUserDataReq.data.userPwd = userPwd.encode()
   if sock.send(loginUserDataReq) == ctypes.sizeof(PollLoginUserDataReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvLoginUserData(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollLoginUserData))
   if  not msgBuf:
      return (None, None)
   loginUserData = PollLoginUserData.from_buffer(bytearray(msgBuf))
   userID = loginUserData.userID.decode().rstrip('\x00')
   userPwd = hashlib.sha256(loginUserData.userPwd).hexdigest()

   return (userID, userPwd)

# Poll logout user
class PollLogoutUserData(ctypes.Structure):
    _fields_ = [('userID', ctypes.c_char * USER_ID_SIZE),
                ('userPwd', ctypes.c_char * USER_PWD_SIZE)]
    _pack_ = 1

class PollLogoutUserDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr)]
    _pack_ = 1

def sendLogoutUserReqMsg(sock):
   logoutUserDataReq = PollLogoutUserDataReq()
   logoutUserDataReq.hdr.msgType = socket.htons(LOGOUT_USER)
   logoutUserDataReq.hdr.flags = socket.htons(1)
   if sock.send(logoutUserDataReq) == ctypes.sizeof(PollLogoutUserDataReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE


# Create poll

class PollChoiceData(ctypes.Structure):
    _fields_ = [('choiceID', ctypes.c_char * CHOICE_ID_SIZE),
                ('choiceName', ctypes.c_char * CHOICE_NAME_SIZE)]
    _pack_ = 1

class CreatePollData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE),
                ('pollName', ctypes.c_char * POLL_NAME_SIZE),
                ('openDateTime', ctypes.c_char * DATE_TIME_SIZE),
                ('closeDateTime', ctypes.c_char * DATE_TIME_SIZE),
                ('pollStatus', ctypes.c_char),
                ('numChoices', ctypes.c_uint16)]
    _pack_ = 1

class CreatePollDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', CreatePollData)]
    _pack_ = 1

def sendCreatePollReqMsg(sock, pollID, pollName, openDateTime, closeDateTime, pollChoices):
   createPollDataReq = CreatePollDataReq()
   createPollDataReq.hdr.msgType = socket.htons(CREATE_POLL)
   createPollDataReq.hdr.flags = socket.htons(1)
   createPollDataReq.data.pollID = pollID.encode()
   createPollDataReq.data.pollName = pollName.encode()
   createPollDataReq.data.openDateTime = openDateTime.encode()
   createPollDataReq.data.closeDateTime = closeDateTime.encode()
   createPollDataReq.data.numChoices = socket.htons(len(pollChoices))

   numChoices = len(pollChoices)
   pollChoiceData = (PollChoiceData * numChoices)()
   for i in range(0, numChoices):
      pollChoiceData[i].choiceID = pollChoices[i][0].encode()
      pollChoiceData[i].choiceName = pollChoices[i][1].encode()
      
   numBytes = sock.send(createPollDataReq)
   if numBytes == ctypes.sizeof(createPollDataReq):
      numBytes += sock.send(pollChoiceData)

   if numBytes == ctypes.sizeof(createPollDataReq) + ctypes.sizeof(pollChoiceData):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvCreatePollData(sock):
   msgBuf = sock.recv(ctypes.sizeof(CreatePollData))
   if  not msgBuf:
      return (None, None, None, None, None)
   createPollData = CreatePollData.from_buffer(bytearray(msgBuf))
   pollID = createPollData.pollID.decode().rstrip('\x00')
   pollName = createPollData.pollName.decode().rstrip('\x00')
   openDateTime = createPollData.openDateTime.decode().rstrip('\x00')
   closeDateTime = createPollData.closeDateTime.decode().rstrip('\x00')
   pollStatus = createPollData.pollStatus.decode().rstrip('\x00')
   numChoices = socket.ntohs(createPollData.numChoices)

   pollChoices = []
   if numChoices:
      msgBuf = sock.recv(ctypes.sizeof(PollChoiceData) * numChoices)
      if  not msgBuf:
         return (None, None, None, None, None)

      pollChoiceData = (PollChoiceData * numChoices).from_buffer(bytearray(msgBuf))
      for i in range(0, numChoices):
         choiceID = pollChoiceData[i].choiceID.decode().rstrip('\x00')
         choiceName = pollChoiceData[i].choiceName.decode().rstrip('\x00')
         pollChoices.append((choiceID, choiceName))

   return (pollID, pollName, openDateTime, closeDateTime, pollChoices)

class AddPollChoicesData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE),
                ('numChoices', ctypes.c_uint16)]

class AddPollChoicesDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', AddPollChoicesData)]
    _pack_ = 1

def sendAddPollChoicesReqMsg(sock, pollID, pollChoices):
   numChoices = len(pollChoices)
   addPollChoicesDataReq = AddPollChoicesDataReq()
   addPollChoicesDataReq.hdr.msgType = socket.htons(POLL_ADD_CHOICES)
   addPollChoicesDataReq.hdr.flags = socket.htons(1)
   addPollChoicesDataReq.data.pollID = pollID.encode()
   addPollChoicesDataReq.data.numChoices = socket.htons(numChoices)

   pollChoiceData = (PollChoiceData * numChoices)()
   for i in range(0, numChoices):
      pollChoiceData[i].choiceID = pollChoices[i][0].encode()
      pollChoiceData[i].choiceName = pollChoices[i][1].encode()

   numBytes = sock.send(addPollChoicesDataReq)
   if numBytes == ctypes.sizeof(addPollChoicesDataReq):
      numBytes += sock.send(pollChoiceData)

   if numBytes == ctypes.sizeof(addPollChoicesDataReq) + ctypes.sizeof(pollChoiceData):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvAddPollChoicesData(sock):
   msgBuf = sock.recv(ctypes.sizeof(AddPollChoicesData))
   if  not msgBuf:
      return (None, None)
   addPollChoicesData = AddPollChoicesData.from_buffer(bytearray(msgBuf))
   pollID = addPollChoicesData.pollID.decode().rstrip('\x00')
   numChoices = socket.ntohs(addPollChoicesData.numChoices)

   msgBuf = sock.recv(ctypes.sizeof(PollChoiceData) * numChoices)
   if  not msgBuf:
      return (None, None)

   pollChoiceData = (PollChoiceData * numChoices).from_buffer(bytearray(msgBuf))
   pollChoices = []
   for i in range(0, numChoices):
      choiceID = pollChoiceData[i].choiceID.decode().rstrip('\x00')
      choiceName = pollChoiceData[i].choiceName.decode().rstrip('\x00')
      pollChoices.append((choiceID, choiceName))

   return (pollID, pollChoices)

class RemovePollChoicesData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE),
                ('numChoices', ctypes.c_uint16)]

class RemovePollChoicesDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', RemovePollChoicesData)]
    _pack_ = 1

def sendRemovePollChoicesReqMsg(sock, pollID, pollChoices):
   numChoices = len(pollChoices)
   removePollChoicesDataReq = RemovePollChoicesDataReq()
   removePollChoicesDataReq.hdr.msgType = socket.htons(POLL_REMOVE_CHOICES)
   removePollChoicesDataReq.hdr.flags = socket.htons(1)
   removePollChoicesDataReq.data.pollID = pollID.encode()
   removePollChoicesDataReq.data.numChoices = socket.htons(numChoices)

   pollChoiceData = (PollChoiceData * numChoices)()
   for i in range(0, numChoices):
      pollChoiceData[i].choiceID = pollChoices[i].encode()

   numBytes = sock.send(removePollChoicesDataReq)
   if numBytes == ctypes.sizeof(removePollChoicesDataReq):
      numBytes += sock.send(pollChoiceData)

   if numBytes == ctypes.sizeof(removePollChoicesDataReq) + ctypes.sizeof(pollChoiceData):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvRemovePollChoicesData(sock):
   msgBuf = sock.recv(ctypes.sizeof(RemovePollChoicesData))
   if  not msgBuf:
      return (None, None)
   removePollChoicesData = RemovePollChoicesData.from_buffer(bytearray(msgBuf))
   pollID = removePollChoicesData.pollID.decode().rstrip('\x00')
   numChoices = socket.ntohs(removePollChoicesData.numChoices)

   msgBuf = sock.recv(ctypes.sizeof(PollChoiceData) * numChoices)
   if  not msgBuf:
      return (None, None)

   pollChoiceData = (PollChoiceData * numChoices).from_buffer(bytearray(msgBuf))
   pollChoices = []
   for i in range(0, numChoices):
      choiceID = pollChoiceData[i].choiceID.decode().rstrip('\x00')
      pollChoices.append(choiceID)

   return (pollID, pollChoices)

class SetPollStatusData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE),
                ('status', ctypes.c_char)]

class SetPollStatusDataReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', SetPollStatusData)]
    _pack_ = 1

def sendSetPollStatusDataReq(sock, pollID, pollStatus):
   setPollStatusDataReq = SetPollStatusDataReq()
   setPollStatusDataReq.hdr.msgType = socket.htons(POLL_SET_STATUS)
   setPollStatusDataReq.hdr.flags = socket.htons(1)
   setPollStatusDataReq.data.pollID = pollID.encode()
   setPollStatusDataReq.data.status = pollStatus.encode()

   if sock.send(setPollStatusDataReq) == ctypes.sizeof(setPollStatusDataReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvSetPollStatusData(sock):
   msgBuf = sock.recv(ctypes.sizeof(SetPollStatusData))
   if  not msgBuf:
      return (None, None)
   setPollStatusData = SetPollStatusData.from_buffer(bytearray(msgBuf))
   pollID = setPollStatusData.pollID.decode().rstrip('\x00')
   status = setPollStatusData.status.decode()

   return (pollID, status)

class PollMakeSelectionReqData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * CHOICE_ID_SIZE),
                ('choiceID', ctypes.c_char * POLL_ID_SIZE)]

class PollMakeSelectionReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', PollMakeSelectionReqData)]
    _pack_ = 1

def sendPollMakeSelectionReq(sock, pollID, choiceID):
   pollMakeSelectionReq = PollMakeSelectionReq()
   pollMakeSelectionReq.hdr.msgType = socket.htons(USER_POLL_MAKE_SELECTION)
   pollMakeSelectionReq.hdr.flags = socket.htons(1)
   pollMakeSelectionReq.data.pollID = pollID.encode()
   pollMakeSelectionReq.data.choiceID = choiceID.encode()

   if sock.send(pollMakeSelectionReq) == ctypes.sizeof(pollMakeSelectionReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvPollMakeSelectionReqData(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollMakeSelectionReqData))
   if  not msgBuf:
      return (None, None)
   pollMakeSelectionReqData = PollMakeSelectionReqData.from_buffer(bytearray(msgBuf))
   pollID = DecodeAndStrip(pollMakeSelectionReqData.pollID)
   choiceID = DecodeAndStrip(pollMakeSelectionReqData.choiceID)

   return (pollID, choiceID)

class ListUsersResponseData(ctypes.Structure):
    _fields_ = [('userID', ctypes.c_char * USER_ID_SIZE),
                ('userName', ctypes.c_char * USER_NAME_SIZE),
                ('userEmail', ctypes.c_char * USER_EMAIL_SIZE)]
    _pack_ = 1

class ListUsersReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr)]
    _pack_ = 1

class ListUsersResponse(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('status', ctypes.c_uint16),
                ('reason', ctypes.c_uint16),
                ('numDataElems', ctypes.c_uint16)]
    _pack_ = 1

def sendListUsersReq(sock):
   listUsersReq = ListUsersReq()
   listUsersReq.hdr.msgType = socket.htons(LIST_USERS)
   listUsersReq.hdr.flags = socket.htons(1)

   if sock.send(listUsersReq) == ctypes.sizeof(listUsersReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def sendListUsersResponse(sock, status, reason, userList):
   listUsersResponse = ListUsersResponse()
   listUsersResponse.hdr.msgType = socket.htons(LIST_USERS)
   listUsersResponse.hdr.flags = socket.htons(2)
   listUsersResponse.status = socket.htons(status)
   listUsersResponse.reason = socket.htons(reason)
   listUsersResponse.numDataElems = socket.htons(len(userList))

   listUsersResponseData = (ListUsersResponseData * len(userList))()

   for i in range(0, len(userList)):
      listUsersResponseData[i].userID = userList[i]['userID'].encode()
      listUsersResponseData[i].userName = userList[i]['userName'].encode()
      listUsersResponseData[i].userEmail = userList[i]['userEmail'].encode()

   expectedNumBytes = ctypes.sizeof(listUsersResponse)
   numBytes = sock.send(listUsersResponse)
   if numBytes == ctypes.sizeof(listUsersResponse) and len(userList) > 0:
      expectedNumBytes += ctypes.sizeof(listUsersResponseData)
      numBytes += sock.send(listUsersResponseData)

   if numBytes == expectedNumBytes:
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvListUsersResponse(sock):
   msgBuf = sock.recv(ctypes.sizeof(ListUsersResponse))
   if  not msgBuf:
      return (None, None, None, None, None)

   listUsersResponse = ListUsersResponse.from_buffer(bytearray(msgBuf))
   msgType = socket.ntohs(listUsersResponse.hdr.msgType)
   flags = socket.ntohs(listUsersResponse.hdr.flags)
   status = socket.ntohs(listUsersResponse.status)
   reason = socket.ntohs(listUsersResponse.reason)
   numDataElems = socket.ntohs(listUsersResponse.numDataElems)

   if msgType != LIST_USERS or flags != 2:
      return None, None, None, None, None

   if status != 0:
      return msgType, flags, status, reason, None

   msgBuf = sock.recv(ctypes.sizeof(ListUsersResponseData) * numDataElems)
   if  not msgBuf:
      return (None, None, None, None, None)

   listUsersResponseData = (ListUsersResponseData * numDataElems).from_buffer(bytearray(msgBuf))

   userList = []

   for i in range(0, numDataElems):
      userList.append({
          'userID': DecodeAndStrip(listUsersResponseData[i].userID),
          'userName': DecodeAndStrip(listUsersResponseData[i].userName),
          'userEmail': DecodeAndStrip(listUsersResponseData[i].userEmail)
      })

   return msgType, flags, status,reason, userList

class PollResultsReqData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE)]
    _pack_ = 1

class PollResultsReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', PollResultsReqData)]
    _pack_ = 1

class PollResultsResponseData(ctypes.Structure):
    _fields_ = [('choiceName', ctypes.c_char * CHOICE_NAME_SIZE),
                ('count', ctypes.c_uint16)]
    _pack_ = 1

class PollResultsResponse(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('status', ctypes.c_uint16),
                ('reason', ctypes.c_uint16),
                ('pollName', ctypes.c_char * POLL_NAME_SIZE),
                ('numDataElems', ctypes.c_uint16)]
    _pack_ = 1

def sendPollGetResultsReq(sock, pollID):
   pollResultsReq = PollResultsReq()
   pollResultsReq.hdr.msgType = socket.htons(USER_POLL_GET_RESULTS)
   pollResultsReq.hdr.flags = socket.htons(1)
   pollResultsReq.data.pollID = pollID.encode()

   if sock.send(pollResultsReq) == ctypes.sizeof(pollResultsReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvPollGetResultsReqData(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollResultsReqData))
   if  not msgBuf:
      return (None, None)
   pollResultsReqData = PollResultsReqData.from_buffer(bytearray(msgBuf))
   pollID = DecodeAndStrip(pollResultsReqData.pollID)

   return (pollID)

def sendPollGetResultsResponse(sock, status, reason, pollName, pollResults):
   pollResultsResponse = PollResultsResponse()
   pollResultsResponse.hdr.msgType = socket.htons(USER_POLL_GET_RESULTS)
   pollResultsResponse.hdr.flags = socket.htons(2)
   pollResultsResponse.status = socket.htons(status)
   pollResultsResponse.reason = socket.htons(reason)
   pollResultsResponse.pollName = pollName.encode()
   pollResultsResponse.numDataElems = socket.htons(len(pollResults))

   pollResultsResponseData = (PollResultsResponseData * len(pollResults))()

   for i in range(0, len(pollResults)):
      pollResultsResponseData[i].choiceName = pollResults[i]['choiceName'].encode()
      pollResultsResponseData[i].count = socket.htons(pollResults[i]['count'])

   expectedNumBytes = ctypes.sizeof(pollResultsResponse)
   numBytes = sock.send(pollResultsResponse)
   if numBytes == expectedNumBytes and len(pollResults) > 0:
      expectedNumBytes +=  ctypes.sizeof(pollResultsResponseData)
      numBytes += sock.send(pollResultsResponseData)

   if numBytes == expectedNumBytes:
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvPollGetResultsResponse(sock):
   msgBuf = sock.recv(ctypes.sizeof(PollResultsResponse))
   if  not msgBuf:
      return None, None, None, None, (None, None)

   pollResultsResponse = PollResultsResponse.from_buffer(bytearray(msgBuf))
   msgType = socket.ntohs(pollResultsResponse.hdr.msgType)
   flags = socket.ntohs(pollResultsResponse.hdr.flags)
   status = socket.ntohs(pollResultsResponse.status)
   reason = socket.ntohs(pollResultsResponse.reason)
   numDataElems = socket.ntohs(pollResultsResponse.numDataElems)
   pollName = DecodeAndStrip(pollResultsResponse.pollName)

   if msgType != USER_POLL_GET_RESULTS or flags != 2:
      return None, None, None, None, (None, None)

   if status != 0:
      return msgType, flags, status, reason, (None, None)

   pollResults = []

   if numDataElems > 0:
      msgBuf = sock.recv(ctypes.sizeof(ListUsersResponseData) * numDataElems)
      if  not msgBuf:
         return (None, None, None, None, None)

      pollResultsResponseData = (PollResultsResponseData * numDataElems).from_buffer(bytearray(msgBuf))

      for i in range(0, numDataElems):
         pollResults.append({
             'choiceName': DecodeAndStrip(pollResultsResponseData[i].choiceName),
             'count': socket.htons(pollResultsResponseData[i].count)
         })

   return msgType, flags, status, reason, (pollName, pollResults)

class ListPollsResponseData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE),
                ('pollName', ctypes.c_char * POLL_NAME_SIZE),
                ('startDate', ctypes.c_char * DATE_TIME_SIZE),
                ('endDate', ctypes.c_char * DATE_TIME_SIZE),
                ('pollStatus', ctypes.c_char)]
    _pack_ = 1

class ListPollsReqData(ctypes.Structure):
    _fields_ = [('pollID', ctypes.c_char * POLL_ID_SIZE)]

class ListPollsReq(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('data', ListPollsReqData)]
    _pack_ = 1

class ListPollsResponse(ctypes.Structure):
    _fields_ = [('hdr', PollMsgHdr),
                ('status', ctypes.c_uint16),
                ('reason', ctypes.c_uint16),
                ('numDataElems', ctypes.c_uint16)]
    _pack_ = 1

def sendListPollsReq(sock, pollID = ""):
   listPollReq = ListPollsReq()
   listPollReq.hdr.msgType = socket.htons(LIST_POLLS)
   listPollReq.hdr.flags = socket.htons(1)
   listPollReq.data.pollID = pollID.encode()

   if sock.send(listPollReq) == ctypes.sizeof(listPollReq):
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvListPollsReqData(sock):
   msgBuf = sock.recv(ctypes.sizeof(ListPollsReqData))
   if  not msgBuf:
      return None
   listPollsReqData = ListPollsReqData.from_buffer(bytearray(msgBuf))
   pollID = DecodeAndStrip(listPollsReqData.pollID)

   return pollID

def sendListPollsResponse(sock, status, reason, pollList):
   listPollResponse = ListPollsResponse()
   listPollResponse.hdr.msgType = socket.htons(LIST_POLLS)
   listPollResponse.hdr.flags = socket.htons(2)
   listPollResponse.status = socket.htons(status)
   listPollResponse.reason = socket.htons(reason)
   listPollResponse.numDataElems = socket.htons(len(pollList))

   listPollResponseData = (ListPollsResponseData * len(pollList))()

   for i in range(0, len(pollList)):
      listPollResponseData[i].pollID = pollList[i]['pollId'].encode()
      listPollResponseData[i].pollName = pollList[i]['pollName'].encode()
      listPollResponseData[i].startDate = pollList[i]['startDate'].encode()
      listPollResponseData[i].endDate = pollList[i]['endDate'].encode()
      listPollResponseData[i].pollStatus = pollList[i]['pollStatus'].encode()

   expectedNumBytes = ctypes.sizeof(listPollResponse)
   numBytes = sock.send(listPollResponse)
   if numBytes == ctypes.sizeof(listPollResponse) and len(pollList) > 0:
      expectedNumBytes += ctypes.sizeof(listPollResponseData)
      numBytes += sock.send(listPollResponseData)

   print(numBytes)
   if numBytes == expectedNumBytes:
      return OP_SUCCESS
   else:
      return OP_FAILURE

def recvListPollsResponse(sock):
   msgBuf = sock.recv(ctypes.sizeof(ListPollsResponse))
   if  not msgBuf:
      return (None, None, None, None, None)

   listPollResponse = ListPollsResponse.from_buffer(bytearray(msgBuf))
   msgType = socket.ntohs(listPollResponse.hdr.msgType)
   flags = socket.ntohs(listPollResponse.hdr.flags)
   status = socket.ntohs(listPollResponse.status)
   reason = socket.ntohs(listPollResponse.reason)
   numDataElems = socket.ntohs(listPollResponse.numDataElems)

   if msgType != LIST_POLLS or flags != 2:
      return None, None, None, None, None

   if status != 0:
      return msgType, flags, status, reason, None

   msgBuf = sock.recv(ctypes.sizeof(ListPollsResponseData) * numDataElems)
   if  not msgBuf:
      return (None, None, None, None, None)

   listPollResponseData = (ListPollsResponseData * numDataElems).from_buffer(bytearray(msgBuf))

   pollList = []

   for i in range(0, numDataElems):
      pollList.append({
          'pollID': DecodeAndStrip(listPollResponseData[i].pollID),
          'pollName': DecodeAndStrip(listPollResponseData[i].pollName),
          'startDate': DecodeAndStrip(listPollResponseData[i].startDate),
          'endDate': DecodeAndStrip(listPollResponseData[i].endDate),
          'pollStatus': DecodeAndStrip(listPollResponseData[i].pollStatus),
          'choices': []
      })

   return msgType, flags, status, reason, pollList

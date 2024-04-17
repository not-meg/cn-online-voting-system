import sys
import sqlite3
import threading
from poll_message_api import *

# Implements all the database operations (i.e adding/modifying/fetch data to/from database)
#
# The database used here is sqlite3. If one were to implement the database using csv or json or
# any other way, just need to replace this file with new implementation and implement all the
# API's in this file.
#
# There are 4 tables used to store the data
#    user_table : This table stores the user details. Primary key is userID
#                 The fields are: userID, userName, userEmail, password
#
#    poll_master_table: This is the master table that stores the poll data. The primary key is pollID
#                 The fields are: pollID, pollName, status, ownerID, startDate, endDate
#
#    poll_choices_table: For each poll the list of choice is stored in this table. The primary key is pollID + choiceID
#                 The fields are: pollID, choiceID, choiceName
#
#    user_poll_selection_table: For each of the poll, the choice made by individual users are stored in this table. The primary key is pollID + userID
#                 The fields are: pollID, userID, choiceID
#

# this is the database file name
POLLSERVER_DB = "poll_database.sqldb"

cl_contexts = []
contextLock = threading.Lock()

def GetThreadContext(cl_sock):
   # CONTEXT LOCK
   contextLock.acquire()
   cntxt = [c for c in cl_contexts if c['socket'] == cl_sock]
   # CONTEXT UNLOCK
   contextLock.release()

   if cntxt:
      return cntxt[0]
   else:
      return None

def RemoveThreadContext(cl_sock):
   # CONTEXT LOCK
   contextLock.acquire()
   cntxt = [i for i in cl_contexts if i['socket'] == cl_sock]
   cl_contexts.remove(cntxt[0])
   contextLock.release()
   # CONTEXT UNLOCK

def AddThreadContext(cl_sock, cl_address, conn, lock):
   # CONTEXT LOCK
   contextLock.acquire()
   cl_contexts.append({'socket': cl_sock,
                       'address': cl_address,
                       'conn': conn,
                       'lock': lock,
                       'userID': None,
                       'logged_in': False})
   # CONTEXT UNLOCK
   contextLock.release()

def ConnectDatabase():
   return sqlite3.connect(POLLSERVER_DB, check_same_thread=False)

def CreateTable(cur, tableName, fields):
   sqlCmd = f"CREATE TABLE {tableName} ({fields})"
   try:
      cur.execute(sqlCmd)
   except sqlite3.OperationalError as opErr:
      print(opErr)

def CreateTables(conn):
   cur = conn.cursor()
   CreateTable(cur, "user_table", "userID, userName, userEmail, password, primary key (userID)")
   CreateTable(cur, "poll_master_table", "pollID, pollName, status, ownerID, startDate, endDate, primary key (pollID)")
   CreateTable(cur, "poll_choices_table", "pollID, choiceID, choiceName, primary key (pollID, choiceID)")
   CreateTable(cur, "user_poll_selection_table", "pollID, userID, choiceID, primary key(pollID, userID)")

   return cur

def AddUser(conn, userID, userName, userEmail, userPwd):
   print(userID, userName, userEmail, userPwd)
   print(len(userID), len(userName), len(userEmail), len(userPwd))

   ### Add duplicate userID, valid userID checks
   if IsUserIDAlreadyExists(conn, userID):
      return (OP_FAILURE, REASON_DUPLICATE_USER_ID)

   status = conn.execute("INSERT INTO user_table VALUES(?, ?, ?, ?)", (userID, userName, userEmail, userPwd))
   print(status)
   status = conn.execute("commit")
   print(status)
   return (OP_SUCCESS, REASON_SUCCESS)

def ChangeUser(conn, userID, userName, userEmail, userPwd):
   print(userID, userName, userEmail, userPwd)
   print(len(userID), len(userName), len(userEmail), len(userPwd))

   ### Add valid user ID check

   status = conn.execute("UPDATE user_table SET userName=?, userEmail=?, password=? WHERE userID=?", (userName, userEmail, userPwd, userID))
   print(status)
   status = conn.execute("commit")
   print(status)
   return (OP_SUCCESS, REASON_SUCCESS)

def IsUserIDAlreadyExists(conn, userID):
   cur = conn.execute("SELECT userID from user_table WHERE userID=?", (userID,))
   data = cur.fetchall()
   if data:
      return True
   return False

def ValidateUser(conn, userID, userPwd):
   cur = conn.execute("SELECT password from user_table WHERE userID=?", (userID,))
   data = cur.fetchall()
   print(userID, userPwd, data)
   if not data:
      status = OP_FAILURE
      reason = REASON_USER_ID_NOT_FOUND
   elif data[0][0] != userPwd:
      status = OP_FAILURE
      reason = REASON_INCORRECT_PWD
   else:
      status = OP_SUCCESS
      reason = REASON_SUCCESS

   return (status, reason)

def AmILoggedIn(userID, cntxt):
   return cntxt['userID'] == userID and cntxt['logged_in']

def IsUserLoggedIn(userID):
   found = [c for c in cl_contexts if c['userID'] == userID and c['logged_in']]
   if found:
      return True
   return False

def SetUserLoggedIn(userID, cntxt):
   if IsUserLoggedIn(userID):
      ret = (OP_FAILURE, REASON_ALREADY_LOGGED_IN)
   else:
      cntxt['userID'] = userID
      cntxt['logged_in'] = True
      ret = (OP_SUCCESS, REASON_SUCCESS)
   return ret

def SetUserLoggedOut(cntxt):
   # CONTEXT LOCK
   contextLock.acquire()
   cntxt['userID'] = None
   cntxt['logged_in'] = False
   contextLock.release()
   # CONTEXT UNLOCK

def ListUsers(cntxt):
   conn = cntxt['conn']
   cur = conn.execute("SELECT * from user_table")
   data = cur.fetchall()
   userList = []
   for r in data:
      userList.append({
            'userID': r[0],
            'userName': r[1],
            'userEmail': r[2],
         })
   return OP_SUCCESS, REASON_SUCCESS, userList
   

def AddPoll(conn, userID, pollID, pollName, openDateTime, closeDateTime, pollChoices):
   if len(pollChoices) < 2:
      return OP_FAILURE, REASON_NOT_ENOUCH_CHOICES

   pollChoices = list(map(lambda c: (pollID,)+c, pollChoices))
   print(conn, userID, pollID, pollName, openDateTime, closeDateTime, pollChoices)
   
   try:
      cur = conn.cursor()
      cur.execute("INSERT INTO poll_master_table VALUES(?, ?, ?, ?, ?, ?)", (pollID, pollName, 'C', userID, openDateTime, closeDateTime))
      if pollChoices:
         cur.executemany("INSERT INTO poll_choices_table VALUES(?, ?, ?)", pollChoices)
      conn.commit()
      status, reason = OP_SUCCESS, REASON_SUCCESS
   except sqlite3.IntegrityError as opErr:
      if opErr.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
         status, reason = OP_FAILURE, REASON_DUP_POLL_DATA
      else:
         status, reason = OP_FAILURE, REASON_DATABASE_ERROR
      conn.rollback()
   
   return status, reason

def IsPollOwnedbyMe(conn, pollID, userID):
   data = conn.execute("SELECT pollID from poll_master_table WHERE (pollID=? and ownerID=?)",
				(pollID, userID)).fetchall()
   if data:
      return True
   return False   

def IsPollIDExists(conn, pollID):
   data = conn.execute("SELECT pollID from poll_master_table WHERE pollID=?", (pollID,)).fetchall()
   if data:
      return True
   return False

def AddPollChoices(conn, pollID, userID, pollChoices):
   pollChoices = list(map(lambda c: (pollID,)+c, pollChoices))
   print(conn, userID, pollID, pollChoices)

   if not IsPollIDExists(conn, pollID):
      return (OP_FAILURE, REASON_NOSUCH_POLL_ID)

   try:
      cur = conn.cursor()
      cur.executemany("INSERT INTO poll_choices_table VALUES(?, ?, ?)", pollChoices)
      conn.commit()
      status, reason = OP_SUCCESS, REASON_SUCCESS
   except sqlite3.IntegrityError as opErr:
      if opErr.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY:
         status, reason = OP_FAILURE, REASON_DUP_POLL_DATA
      else:
         status, reason = OP_FAILURE, REASON_DATABASE_ERROR
      conn.rollback()

   return status, reason

def RemovePollChoices(conn, pollID, userID, pollChoices):

   pollChoices = list(map(lambda c: (pollID, c), pollChoices))
   print(conn, userID, pollID, pollChoices)

   try:
      cur = conn.cursor()
      count = cur.executemany("DELETE FROM poll_choices_table WHERE (pollID=? and choiceID=?)", pollChoices).rowcount
      conn.commit()
      if count == 0:
         status, reason = OP_SUCCESS, REASON_NOSUCH_POLL_ID
      else:
         status, reason = OP_SUCCESS, REASON_SUCCESS
   except sqlite3.IntegrityError as opErr:
      conn.rollback()
      status, reason = OP_FAILURE, REASON_DATABASE_ERROR

   return status, reason

def SetPollStatus(conn, pollID, userID, pollStatus):
   print(conn, userID, pollID, pollStatus)

   if pollStatus not in ['C', 'O']:
      status, reason = OP_FAILURE, REASON_INVALID_POLL_STATUS
   elif not IsPollIDExists(conn, pollID):
      status, reason = OP_FAILURE, REASON_NOSUCH_POLL_ID
   elif not IsPollOwnedbyMe(conn, pollID, userID):
      status, reason = OP_FAILURE, REASON_NOT_OWNER
   else:
      try:
         cur = conn.cursor()
         count = cur.execute("UPDATE poll_master_table SET status=? WHERE " +
                             "(pollID=? and ownerID=?)", (pollStatus, pollID, userID)).rowcount
         conn.commit()
         if count != 1:
            status, reason = OP_FAILURE, REASON_NOSUCH_POLL_ID
         else:
            status, reason = OP_SUCCESS, REASON_SUCCESS
      except sqlite3.IntegrityError as opErr:
         conn.rollback()
         status, reason = OP_FAILURE, REASON_DATABASE_ERROR

   return status, reason

def PollMakeSelection(conn, pollID, userID, choiceID):
   print(conn, userID, pollID, choiceID)

   try:
      cur = conn.cursor()
      polStatus = cur.execute("SELECT status from poll_master_table where (pollID=?)", (pollID,)).fetchall()
      choiceList = cur.execute("SELECT choiceID from poll_choices_table where (pollID=? and choiceID=?)", (pollID,choiceID)).fetchall()
      if len(polStatus) == 0 or len(choiceList) == 0:
         status, reason = OP_FAILURE, REASON_NOSUCH_POLL_ID
      elif polStatus[0][0] != 'O':
         status, reason = OP_FAILURE, REASON_POLL_NOT_OPENED
      else:
         count = cur.execute("UPDATE user_poll_selection_table SET choiceID=? WHERE " +
                          "(pollID=? and userID=?)", (choiceID, pollID, userID)).rowcount
         conn.commit()
         if count == 0:
            cur.execute("INSERT INTO user_poll_selection_table VALUES(?, ?, ?)", (pollID, userID, choiceID))
            conn.commit()
         status, reason = OP_SUCCESS, REASON_SUCCESS
   except sqlite3.IntegrityError as opErr:
      conn.rollback()
      status, reason = OP_FAILURE, REASON_DATABASE_ERROR

   return status, reason

def PollGetResults(conn, pollID):
   pollResults = []
   pollName = conn.execute("SELECT pollName from poll_master_table where (pollID=?)", (pollID,)).fetchall()
   if len(pollName) == 0:
      status, reason = OP_FAILURE, REASON_NOSUCH_POLL_ID
      pollName = None
   else:
      pollName = pollName[0][0]
      cur = conn.execute("SELECT user_poll_selection_table.choiceID, " +
                      "choiceName, count(user_poll_selection_table.choiceID) " +
                      "from user_poll_selection_table INNER " +
                      "JOIN poll_choices_table on (user_poll_selection_table.choiceID == " +
                      "poll_choices_table.choiceID and user_poll_selection_table.pollID == " +
                      "poll_choices_table.pollID) where (user_poll_selection_table.pollID=?) " +
                      "GROUP BY (user_poll_selection_table.choiceID)", (pollID,))

      data = cur.fetchall()
      print(data)
      for r in data:
         pollResults.append({
               'choiceName': r[1],
               'count': int(r[2]),
            })
      status, reason = OP_SUCCESS, REASON_SUCCESS

   return status, reason, pollName, pollResults

def ListPolls(cntxt, pollID):
   conn = cntxt['conn']
   cur = conn.execute("SELECT * from poll_master_table")
   data = cur.fetchall()
   pollList = []
   for r in data:
      pollList.append({
            'pollId': r[0],
            'pollName': r[1],
            'startDate': r[2],
            'endDate': r[2],
            'pollStatus': r[2],
         })
   return OP_SUCCESS, REASON_SUCCESS, pollList

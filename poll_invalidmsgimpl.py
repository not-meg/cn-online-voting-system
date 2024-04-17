import sys
import socket

class InvalidMsgReqImpl:
   def __init__(self, cl_sock, cl_cntxt, conn):
      self.sock = cl_sock
      self.cntxt = cl_cntxt
      self.conn = conn

   def invoke(self):
      print("InvalidMsgReqImpl")
      return 0

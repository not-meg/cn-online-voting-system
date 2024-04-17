#type='String|password|userID|choiceID|pollID'
#[{'type': xx, 'maxLength': xx}]

def validateString(arg):
   return True

def validateUserID(arg):
   return True

def validatePollID(arg):
   return True

def validateChoiceID(arg):
   return True

def validateDateTime(arg):
   return True

def validatePassword(arg):
   return True

validateFuncMap = {
   'String': validateString,
   'userID': validateUserID,
   'pollID': validatePollID,
   'choiceID': validateChoiceID,
   'dateTime': validateDateTime,
   'password': validatePassword
}

def ValidateArguments(choices, args):
   for c in range(0, len(choices)):
      if (choices[c]['type'] not in validateFuncMap or
          len(args[c]) > choices[c]['maxLength'] or
          not validateFuncMap[choices[c]['type']](args[c])):
         return False

   return True

print(ValidateArguments([{'type': 'userID', 'maxLength': 10}], ['user123']))

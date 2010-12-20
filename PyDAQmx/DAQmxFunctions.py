import re
import sys
from ctypes import *
from DAQmxConfig import dot_h_file, lib_name
from DAQmxTypes import *

class DAQError(Exception):
    """Exception raised from the NIDAQ.

    Attributes:
        error -- Error number from NI
        message -- explanation of the error
    """
    def __init__(self, error, mess, fname):
        self.error = error
        self.mess = mess
        self.fname = fname
    def __str__(self):
        return self.mess + '\n in function '+self.fname

def catch_error(f):
    def mafunction(*arg):
        error = f(*arg)
        if error<0:
            errBuff = create_string_buffer(2048)
            DAQmxGetExtendedErrorInfo(errBuff,2048)
            raise DAQError(error,errBuff.value, f.__name__)
        elif error>0:
            errBuff = create_string_buffer(2048)
            DAQmxGetErrorString (error, errBuff, 2048);
            print "WARNING  :",error, "  ", errBuff.value
            raise DAQError(error,errBuff.value)

        return error
    return mafunction
if sys.platform.startswith('win'):        
    DAQlib = windll.LoadLibrary(lib_name)
elif sys.platform.startswith('linux'):
    DAQlib = cdll.LoadLibrary(lib_name)
# else other platforms will already have barfed importing DAQmxConfig

######################################
# Array
######################################
#Depending whether numpy is install or not, 
#the function array_type is defined to return a numpy array or
#a ctype POINTER
try:
    import numpy
except ImportError:
    def array_type(string):
        return eval('POINTER('+string+')')
else:
    # Type conversion for numpy
    def numpy_conversion(string):
	""" Convert a type given by a string to a numpy type

        """
        #This function uses the fact that the name are the same name, 
        #except that numpy uses lower case
	return eval('numpy.'+string.lower())
    def array_type(string):
	""" Returns the array type required by ctypes when numpy is used """
        return numpy.ctypeslib.ndpointer(dtype = numpy_conversion(string))

################################
#Read the .h file and convert the function for python
################################
include_file = open(dot_h_file,'r') #Open NIDAQmx.h file

################################
# Regular expression to parse the NIDAQmx.h file
# Almost all the function define in NIDAQmx.h file are imported
################################
fonction_parser = re.compile(r'.* (DAQ\S+)\s*\((.*)\);')
const_char = re.compile(r'(const char)\s*([^\s]*)\[\]')
string_type = '|'.join(['int8','uInt8','int16','uInt16','int32','uInt32','float32','float64','int64','uInt64','bool32','TaskHandle'])

simple_type = re.compile('('+string_type+')\s*([^\*\[]*)\Z')
pointer_type = re.compile('('+string_type+')\s*\*([^\*]*)\Z')
pointer_type2 = re.compile('('+string_type+')\s*([^\s]*)\[\]\Z')
char_etoile = re.compile(r'(char)\s*\*([^\*]*)\Z') # match "char * name"
void_etoile = re.compile(r'(void)\s*\*([^\*]*)\Z') # match "void * name"
char_array = re.compile(r'(char)\s*([^\s]*)\[\]') # match "char name[]"
dots = re.compile('\.\.\.')
call_back = re.compile(r'([^\s]*CallbackPtr)\s*([^\s]*)') # Match "DAQmxDoneEventCallbackPtr callbackFunction"

function_list = [] # The list of all function 
# function_dict: the keys are function name, the value is a dictionnary 
# with 'arg_type' and 'arg_name', the type and name of each argument 
function_dict = {} 


for line in include_file:
    line = line[0:-1]
    if re.search("int32",line):
        if fonction_parser.match(line):
            name = fonction_parser.match(line).group(1)
            function_list.append(name)
            arg_string = fonction_parser.match(line).group(2)
            arg_list=[]
            arg_name = []
            for arg in re.split(',',arg_string):
                if const_char.search(arg):
                    arg_list.append(c_char_p)
                    arg_name.append(const_char.search(arg).group(2))
                elif simple_type.search(arg): 
                    arg_list.append( eval(simple_type.search(arg).group(1)))
                    arg_name.append(simple_type.search(arg).group(2))
                elif pointer_type.search(arg): 
                    arg_list.append( eval('POINTER('+pointer_type.search(arg).group(1)+')') )
                    arg_name.append(pointer_type.search(arg).group(2))
                elif pointer_type2.search(arg):
                    if pointer_type2.search(arg).group(2) == 'readArray' or pointer_type2.search(arg).group(2) == 'writeArray':
                        arg_list.append(array_type(pointer_type2.search(arg).group(1)))
                    else:    
                        arg_list.append( eval('POINTER('+pointer_type2.search(arg).group(1)+')') )
                        arg_name.append(pointer_type2.search(arg).group(2))
                elif char_etoile.search(arg):
                    arg_list.append(c_char_p)
                    arg_name.append(char_etoile.search(arg).group(2))
                elif void_etoile.search(arg):
                    arg_list.append(c_void_p)
                    arg_name.append(void_etoile.search(arg).group(2))
                elif char_array.search(arg):
                    arg_list.append(c_char_p)
                    arg_name.append(char_array.search(arg).group(2))
                elif call_back.search(arg):
                    arg_list.append( eval(call_back.search(arg).group(1)) )
                    arg_name.append(call_back.search(arg).group(2))                        
                elif dots.search(arg):
                    pass
                else:
                    pass
                function_dict[name] = {'arg_type':arg_list, 'arg_name':arg_name}                
                cmd1 = name+' =  catch_error( DAQlib.'+name+' )'
                cmd2 = 'DAQlib.'+name+'.argtypes = arg_list'
                exec(cmd1)
                exec(cmd2)

include_file.close()

# Functions using callback in NIDAQmx.h 
#DAQmxRegisterEveryNSamplesEvent = catch_error( DAQlib.DAQmxRegisterEveryNSamplesEvent )
#DAQmxRegisterEveryNSamplesEvent.argtypes = [TaskHandle,int32, uInt32, uInt32, type(DAQmxRegisterEveryNSamplesEvent), c_void_p]

#DAQmxRegisterDoneEvent = catch_error( DAQlib.DAQmxRegisterDoneEvent )
#DAQmxRegisterDoneEvent.argtypes = [TaskHandle, uInt32, type(DAQmxDoneEventCallbackPtr) , c_void_p]

#DAQmxRegisterSignalEvent = catch_error( DAQlib.DAQmxRegisterSignalEvent)
#DAQmxRegisterSignalEvent.argtypes = [TaskHandle,int32, uInt32, type(DAQmxRegisterSignalEvent), c_void_p]

 





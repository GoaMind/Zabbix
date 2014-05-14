#!/usr/bin/python
import subprocess
import sys
import os

### USER CONFIGURABLE PARAMETERS

# As JAVA_HOME might not be defined - Configure paths to jps and jstat below
jps = '/usr/java/default/bin/jps'
jstat = '/usr/java/default/bin/jstat'

# Zabbix parameters
zabbix_key = 'custom.proc.java'						# Zabbix key root - Full key is zabbix_key.process_name[metric]
zabbix_sender = "/usr/bin/zabbix_sender"			# Path to zabbix_sender binary
zabbix_conf = "/etc/zabbix/zabbix_agentd.conf"		# Path to Zabbix agent configuration
send_to_zabbix = 1									# Send data to zabbix ? > 0 is yes / 0 is No + debug output


def usage():
	"""Display program usage"""

	print "\nUsage : ", sys.argv[0], " process_name alive|mem|all"
	print "process_name : java process name as seen in jps output"
	print "Modes : \n\talive : Return number of running process\n\tmem : Send memory stats\n\tall : Do both"
	sys.exit(1)


class Jprocess:
	"""Check java process presence and get memory stats"""

	def __init__(self, arg):
		"""Initialize default values"""

		self.pdict = {		# Java process dictonary, put all process info inside
		"jpname": arg, 		# Process name as seen in jps output
		"nproc": 0,			# Number of process found - default is 0
		}

		self.zdict = {		# Contains only data that will be sent to Zabbix
		"heap_used" : 0,
		"heap_max" : 0,
		"perm_used" : 0,
		"perm_max"  : 0,
		}

		

	def chk_proc(self):
		"""Check if java process is running / Get its PID"""

# Get jps output
		jpsout = subprocess.Popen(['sudo', jps], stdout=subprocess.PIPE)

# Parse every lines
		for line in jpsout.stdout:
			line = line.rstrip('\n')
			pid, name = line.split(' ',1)
# If name matches user's input, record PID and increment nproc
			if name == self.pdict['jpname']:
				self.pdict['pid'] = pid
				if send_to_zabbix == 0: print "Process found :", name, "with pid :", self.pdict['pid']
				self.pdict['nproc'] += 1

	def get_jstats(self):
		"""Check if java process is running"""

# Do nothing if no process were found - Default values are 0		
		if self.pdict['nproc'] == 0:
			return False
# Get gc and gccapacity from jstat and put them in pdict dictionary		
		self.pdict.update(self.fill_jstats("-gc"))
		self.pdict.update(self.fill_jstats("-gccapacity"))

		if send_to_zabbix == 0: print "\nDumping collected stat dictionary\n-----\n", self.pdict, "\n-----\n"
		


	def fill_jstats(self, opts):
		"""Return a dictionary with jstat values"""

		if send_to_zabbix == 0: print "Getting", opts, "stats for process", self.pdict['pid'], "with command : sudo", jstat, opts, self.pdict['pid']
# Get jstat output
		jstatout = subprocess.Popen(['sudo', jstat, opts, self.pdict['pid']], stdout=subprocess.PIPE)
		stdout, stderr = jstatout.communicate()
# Build dictionary
		legend, data = stdout.split('\n',1)
		mydict = dict(zip(legend.split(), data.split()))

		return mydict

	def compute_jstats(self):
		"""Compute stats not given directly by jstat"""

# Do nothing if no process were found - Default values are 0
		if self.pdict['nproc'] == 0:
			return False

# Put perm gen stat in zabbix dictionary - No need to compute anything here
		self.zdict['perm_used'] = round(float(self.pdict['PU']) * 1024,2)
		self.zdict['perm_max'] = round(float(self.pdict['PGCMX']) * 1024,2)

# Compute heap size used/max = Eden + Old space
		self.zdict['heap_used'] = round(((float(self.pdict['EU']) + float(self.pdict['OU'])) * 1024),2)
		self.zdict['heap_max'] = round(((float(self.pdict['NGCMX']) + float(self.pdict['OGCMX'])) * 1024),2)

		if send_to_zabbix == 0: print "Dumping zabbix stat dictionary\n-----\n", self.zdict, "\n-----\n"


	def send_to_zabbix(self, metric):
		"""Send stat to zabbix via zabbix_sender"""

# Generate zabbix key => zabbix_key.process_name[metric]
		key = zabbix_key  + '.' + self.pdict['jpname'].lower() + "[" + metric + "]"

# Call zabbix_sender if send_to_zabbix > 0
		if send_to_zabbix > 0:
		 	try:
		   		subprocess.call([zabbix_sender, "-c", zabbix_conf, "-k", key, "-o", str(self.zdict[metric])], stdout=FNULL, stderr=FNULL, shell=False)		# Call zabbix_sender
		 	except OSError, detail:
   				print "Something went wrong while exectuting zabbix_sender : ", detail
   		else:
   			print "Simulation: the following command would be execucted :\n", zabbix_sender, "-c", zabbix_conf, "-k", key, "-o", str(self.zdict[metric]), "\n"




# List of accepted mode --- alive : Return number of running process - mem : Send memory stats - all : Do both"

accepted_modes = ['alive', 'mem', 'all']

# Check args

if len(sys.argv) == 3 and sys.argv[2] in accepted_modes:
	procname = sys.argv[1]
	mode = sys.argv[2]
else:
	usage()


# Check if process is running / Get PID
jproc = Jprocess(procname) 
jproc.chk_proc()

# If mode is alive or all - print number of process found
if mode == "alive" or mode == "all":
		print jproc.pdict["nproc"]
		if send_to_zabbix == 0: print "There is ", jproc.pdict['nproc'], "running process named", jproc.pdict['jpname']
# If mem only print 0
else:
		print "0"

# If mode is mem or all - Get memory stats and send them to zabbix.
if mode == "mem" or mode == "all":
	jproc.get_jstats()
	jproc.compute_jstats()
	FNULL = open(os.devnull, 'w')		# Open devnull to redirect zabbix_sender output
	for key in jproc.zdict:
		jproc.send_to_zabbix(key)
		# print key, jproc.zdict[key]
		# print "Zkey = ", zabbix_key  + '.' + jproc.pdict['jpname'].lower() + "[" + key + "]"
	FNULL.close()


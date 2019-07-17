# ------------------------------------------------------------------------------------ #
# The only command allowed on eCar service from our side: [PUT]
# /EnergyService/api/command/module
#
# Content Body:
# {
#  "sessionID": "string",
#  "cpId": 0,
#  "price": "string",
#  "getiMaxSession": 0,
#  "gettMaxSession": 0,
#  "geteMaxSession": 0,
#  "cuCd": "string",
#  "reason": "string"
#}
#
# ------------------------------------------------------------------------------------ #
@app.route("/S4G/api/command/module",methods=['PUT'])
def modulateCharge():
	description = "[EconomicServer][HTTPS][PUT] S4G Service to modulate charge process"
	if(enablePrints == True):
		print(str(description))	

	try:

		req_data      = request.get_json()	

		# Verify reponse content (return True if successful)!
		if(analyzeRequest(req_data) == False):
			description = "[EconomicServer][modulateCharge] Request Error: " + str(req_data)
			if(enablePrints == True):
				print(description)
			return str(description)

		# print("Analyzed json: " + str(type(req_data)))
		print("[EconomicServer][modulateCharge] Analyzed json content: " + str(req_data))

		payload = parseRequest(req_data)

		print("[EconomicServer][modulateCharge] Parsed json")

		# dest = str(SiemensAddress)+":"+str(SiemensPort)+str(SiemensEndpoint)
		# dest = str(SiemensAddress)+str(SiemensEndpoint)
		dest = "https://oc.electromobility.siemens.it/EnergyService/api/command/module"

		if(enablePrints == True):
			print("[EconomicServer] Modulate towards following destination: " + str(dest))
			print("[EconomicServer] Modulate with following payload: " + str(payload))

		return "[EconomicServer][modulateCharge] TEMPORARY Return"

		r = requests.put(dest, data=payload)

		# Verify via status code if Server responded!
		if(r.status_code != 200):
			print("[EconomicServer] Response Error: " + r)
			return False

		# Verify reponse content (return True if successful)!
		if(analyzeResponse(r.content) == False):
			description = "[EconomicServer] Response Error: " + str(r)
			if(enablePrints == True):
				print(description)
			return str(description)

		if(enablePrints == True):
			print("[EconomicServer][modulateCharge] Full Response: " + r)

		# --------------------------------------------------------------------- #		
		# If we reached this point then it means that we sent a proper request!
		# This request should be exploited by the Siemens server to trigger
		# the appropriate recharging rule on the deployment via OCPP
		# --------------------------------------------------------------------- #
		description = "Success"

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][modulateCharge] S4G Service Parsing Error %s" %e)
		return str("[EconomicServer][modulateCharge] S4G Service Parsing Error %s" %e)

	return str(description)

# ------------------------------------------------------------------------------------ #
# Agreed Payload MUST be on SENML format:
#{
#	"bn": "Charger_name"
#	"n": "EV_name_or_id/SoC",
#	"t": 1557354938.0,
#	"v":0.0,
#	"u":"%"
#}
def parseRequest(payload):
	# --------------------------------------------------------------------- #
	# Extract main field from request and build the real one
	# --------------------------------------------------------------------- #
	chargerName = payload['bn']
	EV_id       = payload['n']
	timestamp   = payload['t']
	value       = payload['v']
	unit        = payload['u']

	if(enablePrints == True):
		print("[EconomicServer][parseRequest] chargerName: " + str(chargerName))
		print("[EconomicServer][parseRequest] EV_id: "       + str(EV_id))
		print("[EconomicServer][parseRequest] timestamp: "   + str(timestamp))
		print("[EconomicServer][parseRequest] value: "       + str(value))
		print("[EconomicServer][parseRequest] unit: "        + str(unit))

	# --------------------------------------------------------------------- #
	# Procedure to get ID of interests 
	# --------------------------------------------------------------------- #
	sessionID    = "sessionID"
	cpId         = "cpId"
	price        = ""
	iMaxSession  = str(value)
	tMaxSession  = ""
	eMaxSession  = ""
	cuCd         = "cuCd"
	reason       = "Test"

	# --------------------------------------------------------------------- #
	# Build the real request towards the Siemens Server
	# --------------------------------------------------------------------- #
	#{
	#	"sessionID" : "33012",
	#	"cpId" : "2",
	#	"price" : "1",
	#	"iMaxSession" : "15000",
	#	"tMaxSession" : "",
	#	"eMaxSession" : "",
	#	"cuCd" : "SIEMENS_P0000037",
	#	"reason" : "provax"
	#}
	realRequest = {}
	realRequest['sessionID']   = sessionID
	realRequest['cpId']        = cpId
	realRequest['price']       = price
	realRequest['iMaxSession'] = iMaxSession
	realRequest['tMaxSession'] = tMaxSession
	realRequest['eMaxSession'] = eMaxSession
	realRequest['cuCd']        = cuCd
	realRequest['reason']      = reason


	return str(realRequest)


def analyzeRequest(payload):
	# --------------------------------------------------------------------- #
	# Request Parsing
	# --------------------------------------------------------------------- #
	return True


def analyzeResponse(payload):
	# --------------------------------------------------------------------- #
	# Response Parsing
	# --------------------------------------------------------------------- #
	return True

# ------------------------------------------------------------------------------------ #
# INTERNAL API:
# ------------------------------------------------------------------------------------ #
# The following GET API will be provided on the VPN for S4G Internal Purposes
# [Enabling PROFEV]
#
# Example of Message:
# [...]
@app.route("/S4G/status/list",methods=['GET'])
def statusList():
	description = "[EconomicServer] S4G Service Charging Unit Status list"
	try:

		if(enablePrints == True):
			print(str(description))	
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP           (10.8.0.x)
		# Localhost        (127.0.0.1)		
		# Localhost-Docker (172.17.0.1)
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = join_Status(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][statusList] S4G Service [GET] Parsing Error %s" %e)
		return str("[EconomicServer][statusList] S4G Service [GET] Parsing Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/status/cu/<id>",methods=['GET'])
def cuStatus(id):
	description = "[EconomicServer] S4G Service Charging Unit Status"

	try:
		if(enablePrints == True):
			print(str(description))	
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_cuStatus_by_id(conn,id)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][cuStatus] S4G Service [GET] Parsing Error %s" %e)
		return str("[EconomicServer][cuStatus] S4G Service [GET] Parsing Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/status/meter/<id>",methods=['GET'])
def meterStatus(id):
	description = "[EconomicServer] S4G Service Meter Status"

	try:
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_meterStatus_by_id(conn,id)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][meterStatus] S4G Service [GET] Parsing Error %s" %e)
		return str("[EconomicServer][meterStatus] S4G Service [GET] Parsing Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/cu/list",methods=['GET'])
def cuList():
	description = "[EconomicServer] S4G Service Charging Unit list"

	try:
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_all_cu(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][cuList] S4G Service [GET] Parsing Error %s" %e)
		return str("[EconomicServer][cuList] S4G Service [GET] Parsing Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
@app.route("/S4G/cu/<idCU>",methods=['GET'])
def cuSingle(idCU):
	description = "[EconomicServer] S4G Service Single Charging Unit:"

	try:

		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_cu_by_id(conn,idCU)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][cuSingle] S4G Service [GET] Parsing Error %s" %e)
		return str("[EconomicServer][cuSingle] S4G Service [GET] Parsing Error %s" %e)

	return res

# ------------------------------------------------------------------------------------ #
def cuSingleRetrieval(idCU):
	description = "[EconomicServer] S4G Service Single Charging Unit retrieval:"
	if(enablePrints == True):
		print(str(description))

	try:
		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_cu_by_id(conn,idCU)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][cuSingleRetrieval] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][cuSingleRetrieval] S4G Service [GET] DB Error %s" %e)

	return res

# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/meter/list",methods=['GET'])
def meterList():
	description = "[EconomicServer] S4G Service Meter list"

	try:
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_all_meter(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][meterList] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][meterList] S4G Service [GET] DB Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
@app.route("/S4G/meter/<idMeter>",methods=['GET'])
def meterSingle(idMeter):
	description = "[EconomicServer] S4G Service Single Meter: "
	
	try:
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_meter_by_id(conn,idMeter)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][meterSingle] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][meterSingle] S4G Service [GET] DB Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/plug/list",methods=['GET'])
def plugList():
	description = "[EconomicServer] S4G Service Plug list"

	try:

		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_all_plug(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][plugList] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][plugList] S4G Service [GET] DB Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/plug/<idPlug>",methods=['GET'])
def plugSingle(idPlug):
	description = "[EconomicServer] S4G Service Single Plug: "

	try:

		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_plug_by_id(conn,idPlug)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][plugSingle] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][plugSingle] S4G Service [GET] DB Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# SESSIONS MANAGEMENT:
# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/session/<idSession>",methods=['GET'])
def sessionSingle(idSession):
	description = "S4G Service session"

	try:

		if(enablePrints == True):
			print(str(description) + str(idSession))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_startSession_by_id(conn,idPlug)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][sessionSingle] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][sessionSingle] S4G Service [GET] DB Error %s" %e)

	return res


# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/active/sessions",methods=['GET'])
def activeSessionList():
	description = "S4G Service active sessions (started but not yet ended)"

	try:
		if(enablePrints == True):
			print(str(description))	
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")

		# ------------------------------------- #
		# For each started session,
		# verify if it is ended or not.
		# ------------------------------------- #
		conn = create_connection(persistentDB)
		if conn is not None:
			start = select_all_startSession(conn)

			end = select_all_endSession(conn)

			close_connection(conn)

		parsedResult = json.loads(start)
		parsedEnd    = json.loads(end)

		activeSessions = []

		for x in parsedResult['startSession']:
			alreadyClosed = False
			# Extract the sessionID
			sessionID = x['sessionID']
			# Verify if sessionID is already closed
			for y in parsedEnd['endSession']:
				if(sessionID == y['sessionID']):
					alreadyClosed = True

			if(alreadyClosed == False):
				activeSessions.append(x)

		data_json = json.dumps({'activeSession':activeSessions})

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][activeSessionList] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][activeSessionList] S4G Service [GET] DB Error %s" %e)

	return data_json

# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/start/sessions",methods=['GET'])
def startSessionList():
	try:
		description = "S4G Service start sessions"
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_all_startSession(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][startSessionList] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][startSessionList] S4G Service [GET] DB Error %s" %e)

	return res

# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/start/session/<sessionID>",methods=['GET'])
def startSessionSingle(sessionID):
	try:
		description = "S4G Service start session"
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_startSession_by_id(conn,sessionID)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][startSessionSingle] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][startSessionSingle] S4G Service [GET] DB Error %s" %e)

	return res



# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/update/sessions",methods=['GET'])
def updateSessionList():
	try:
		description = "S4G Service update sessions"
		if(enablePrints == True):
			print(str(description))	
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_all_updateSession(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][updateSessionList] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][updateSessionList] S4G Service [GET] DB Error %s" %e)

	return res

# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/end/sessions",methods=['GET'])
def endSessionList():
	try:
		description = "S4G Service end sessions"
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	


		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_all_endSession(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][endSessionList] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][endSessionList] S4G Service [GET] DB Error %s" %e)

	return res

# ------------------------------------------------------------------------------------ #
# Example of Message:
# [...]
@app.route("/S4G/end/session/<sessionID>",methods=['GET'])
def endSessionSingle(sessionID):
	try:
		description = "S4G Service end session"
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = select_endSession_by_id(conn,sessionID)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][endSessionSingle] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][endSessionSingle] S4G Service [GET] DB Error %s" %e)

	return res
# ------------------------------------------------------------------------------------ #
# !!!WARNING!!! 
# ENABLE ONLY IN CASE OF DEBUG!
# if(localDebug == True):
# Example of Message:
# [...]
@app.route("/S4G/deleteall/sessions",methods=['GET'])
def deleteSessions():
	try:
		description = "S4G delete all stored session"
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = delete_allSessions(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][deleteSessions] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][deleteSessions] S4G Service [GET] DB Error %s" %e)

	return res

# Example of Message:
# [...]
@app.route("/S4G/deleteall/cu",methods=['GET'])
def deleteCU():
	try:
		description = "S4G delete all stored CU, meters and plugs"
		if(enablePrints == True):
			print(str(description))
			print("Requester: " + str(request.remote_addr))
		# -------------------------------------- #
		# Filter all the incoming request!
		# This is an internal service!
		# Only allowed IP range are:
		# VPN-IP    (10.8.0.x)
		# Localhost (127.0.0.1)		
		# str.startswith(substring)
		# -------------------------------------- #	
		if(request.remote_addr != "172.17.0.1" and request.remote_addr != "127.0.0.1" and "10.8.0." not in request.remote_addr):
			return str("You are not Allowed to perform the current request! INTERNAL API!")	

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			res = delete_allCU(conn)

			close_connection(conn)

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer][deleteCU] S4G Service [GET] DB Error %s" %e)
		return str("[EconomicServer][deleteCU] S4G Service [GET] DB Error %s" %e)

	return res

# ------------------------------------------------------------------------------------ #
# INTERNAL Methods:
# ------------------------------------------------------------------------------------ #
def updateSessions(receivedData,state):
	if(enablePrints == True):
		print("[EconomicServer] Update sessions")

	if(str(state) not in knownStates):
		print("[EconomicServer] Wrong State reference: " + str(state))
		return 

	if(type(receivedData)==dict):
		if(enablePrints == True):
			print("[EconomicServer] List found")
		tmplist=list(receivedData.values())

	try:
		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			if(str(state) == "new"):
				if(enablePrints == True):
					print("[EconomicServer] New Session: ")
					print(tmplist)
				add_NewSession(conn,tmplist)

			elif(str(state) == "update"):	
				if(enablePrints == True):
					print("[EconomicServer] Update Session")
					print(receivedData)
				add_UpdateSession(conn,tmplist)

			elif(str(state) == "end"):	
				if(enablePrints == True):
					print("[EconomicServer] End Session")
					print(receivedData)
				add_EndSession(conn,tmplist)
			else:
				print("[updateSessions] Error! cannot create the database connection.")
				raise Exception('[updateSessions] Error! cannot create the database connection')
	except Exception as e:
		if(conn is not None):		
			close_connection(conn)

		if(enablePrints == True):
			print("[EconomicServer] Sessions not found or UNIQUE rule not applied: %s" %e)

		return 

	if(enablePrints == True):
		print("[EconomicServer] Update persistent configuration")	

	close_connection(conn)

# ------------------------------------------------------------------------------------ #
def updateConfiguration(receivedData,operation,table,foreign=0):
	if(enablePrints == True):
		print("[EconomicServer] Open persistent configuration")

	if(str(table) not in knownTables):
		print("[EconomicServer] Wrong TABLE reference: " + str(table))
		return 

	if(str(operation) not in knownOperations):
		print("[EconomicServer] Wrong OPERATION reference: " + str(operation))
		return 

	try:
		# To adapt in case of list of values or simply the id (key) referring to the row of interest
		# if(type(receivedData)==list or type(receivedData)==dict):
		if(type(receivedData)==dict):
			if(enablePrints == True):
				print("[EconomicServer] List found")
			tmplist=list(receivedData.values())
		else:
			tmplist=receivedData
			if(enablePrints == True):
				print("[EconomicServer] Single Value found " + str(tmplist))

		#print("[EconomicServer] updateConfiguration before conn")
		# create a database connection
		conn = create_connection(persistentDB)
		#print("[EconomicServer] updateConfiguration after conn")
		if conn is not None:
			if(str(operation) == "add"):
				if(enablePrints == True):
					print("[EconomicServer] Add receivedData on: "+ str(table))
					# print("[EconomicServer] receivedData(dict): "+ str(receivedData))				
					# print("[EconomicServer] receivedData(list): "+ str(tmplist))

				# This procedure will fail properly in case entry already exist!
				if(str(table) == "plugs"):
					tmplist.append(foreign)
					if(enablePrints == True):
						print("[EconomicServer] uniqueData(list): "+ str(tmplist))
					create_plug(conn,tmplist)
				elif(str(table) == "meters"):
					# Remove inner structures
					meterlist = [x for x in tmplist if type(x)!=dict and type(x)!=list]
					meterlist.append(foreign)
					if(enablePrints == True):
						print("[EconomicServer] uniqueData(list): "+ str(meterlist))

					create_meter(conn,meterlist)
				elif(str(table) == "cu"):
					if(enablePrints == True):
						print("[EconomicServer] uniqueData(list): "+ str(tmplist))
					create_cu(conn,tmplist)

			elif(str(operation) == "modify"):
				# IT IS REQUIRED THE KEY TO FIND!
				# EXTRACT IT FROM THE GIVEN STRUCTS!
				# and APPEND IT AT THE END!
				
				if(enablePrints == True):
					print("[EconomicServer] Modify receivedData on: "+ str(table))
					print("[EconomicServer] Modify receivedData on: "+ str(tmplist))

				if(str(table) == "plugs"):
					tmplist.append(foreign)
					tmplist.append(receivedData['plugId'])
					if(enablePrints == True):
						print("[EconomicServer] uniqueData(list): "+ str(tmplist))
					update_plug(conn,tmplist)
				elif(str(table) == "meters"):
					# Remove inner structures
					meterlist = [x for x in tmplist if type(x)!=dict and type(x)!=list]
					meterlist.append(foreign)
					meterlist.append(receivedData['meterCuId'])

					if(enablePrints == True):
						print("[EconomicServer] uniqueData(list): "+ str(meterlist))

					update_meter(conn,meterlist)
				elif(str(table) == "cu"):
					tmplist.append(receivedData['cuCd'])
					update_cu(conn,tmplist)

			elif(str(operation) == "remove"):
				if(enablePrints == True):
					print("[EconomicServer] Remove receivedData on: "+ str(table))
				if(str(table) == "plugs"):
					delete_plug(conn,tmplist)
				elif(str(table) == "meters"):
					delete_meter(conn,tmplist)
				elif(str(table) == "cu"):
					delete_cu(conn,tmplist)
		else:
			print("[updateConfiguration] Error! cannot create the database connection.")
			raise Exception('[updateConfiguration] Error! cannot create the database connection')

	except Exception as e:
		if(conn is not None):		
			close_connection(conn)

		if(enablePrints == True):
			print("[EconomicServer] Configuration not found or UNIQUE rule not applied: %s" %e)

		return 

	if(enablePrints == True):
		print("[EconomicServer] Update persistent configuration")	

	close_connection(conn)

# ------------------------------------------------------------------------------------ #
# Previously stored data (tecnical information about Siemens Machines)
# Initialization of Database!
# Ok, but let's start with a predefined database already configured!
# ------------------------------------------------------------------------------------ #
#					DEPRECATED
# ------------------------------------------------------------------------------------ #
def restoreDataConfiguration():
	if(enablePrints == True):
		print("[EconomicServer] Open configuration")
	try:

		# create a database connection
		conn = create_connection(persistentDB)
		if conn is not None:
			# --------------------------------------------------- #
			# CHARGING UNITS DETAILS
			# --------------------------------------------------- #
			# create cu table if not exists
			create_table(conn, sql_create_cu_table)
			# create meters table if not exists 
			create_table(conn, sql_create_meters_table)
			# create plugs table if not exists
			create_table(conn, sql_create_plugs_table)
			# --------------------------------------------------- #
			# RECHARGING SESSIONS
			# --------------------------------------------------- #
			# create plugs table if not exists
			create_table(conn, sql_create_session_start_table)
			# create plugs table if not exists
			create_table(conn, sql_create_session_update_table)
			# create plugs table if not exists
			create_table(conn, sql_create_session_end_table)
			# --------------------------------------------------- #	
			# CHARGING UNIT STATUS
			# --------------------------------------------------- #	
			# create CU Status table if not exists
			create_table(conn, sql_create_cu_status_table)
			# create Meters Status table if not exists
			create_table(conn, sql_create_meters_status_table)
			# --------------------------------------------------- #			
		else:
			print("Error! cannot create the database connection.")
			raise Exception('Error! cannot create the database connection')
	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer] Configuration not possible: %s" %e)

		if(conn is not None):		
			close_connection(conn)
		return 

	if(enablePrints == True):
		print("[EconomicServer] Update run-time configuration")	

	close_connection(conn)


# ------------------------------------------------------------------------------------ #
# MAIN SQLITE3 PERSISTENCE RELATED FUNCTIONS:
# ------------------------------------------------------------------------------------ #
def create_connection(db_file):
	""" create a database connection to the SQLite database
		specified by db_file
	:param db_file: database file
	:return: Connection object or None
	"""
	try:
		conn = sqlite3.connect(db_file)
		return conn
	except Exception as e:
		print(e)

	return None
# ------------------------------------------------------------------------------------ #
def close_connection(conn):
	""" close a database connection with the SQLite database
	:param conn: database cursor
	"""
	try:			
		# Save (commit) the changes
		conn.commit()

		# We can also close the connection if we are done with it.
		# Just be sure any changes have been committed or they will be lost.
		conn.close()
	except Exception as e:
		print(e)


# ------------------------------------------------------------------------------------ #
def create_table(conn, create_table_sql):
	""" create a table from the create_table_sql statement
	:param conn: Connection object
	:param create_table_sql: a CREATE TABLE statement
	:return:
	"""
	try:
		c = conn.cursor()
		c.execute(create_table_sql)
	except Exception as e:
		print(e)

# ------------------------------------------------------------------------------------ #
# CHARGING UNITS STATUS
# Methods for dedicated SQL purposes:
# ------------------------------------------------------------------------------------ #
def create_cuStatus(conn, cu):
	"""
	Create a new CU Status into the cuStatus table
	:param conn:
	:param cuStatus:
	:return: cuStatus id
	"""
	sql = ''' INSERT INTO cuStatus(cuState,sn,cuCode,timestamp) VALUES(?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, cu)
	# 
	return cur.lastrowid
# ------------------------------------------------------------------------------------ #
def update_cuStatus(conn, cuS):
	"""
	update cuStatus
	:param conn:
	:param cu:
	:return: cuStatus id
	"""
	sql = ''' UPDATE cuStatus
              SET cuState = ? ,
                  sn = ?,
                  cuCode = ? ,
                  timestamp = ?
              WHERE cuCode = ?'''
	cur = conn.cursor()
	cur.execute(sql, cuS)
# ------------------------------------------------------------------------------------ #
def create_meterStatus(conn, meterS):
	"""
	Create a new Meter Status into the meterStatus table
	:param conn:
	:param meter:
	:return: meter id
	"""
	sql = ''' INSERT INTO meterStatus(meterID,socketID,meterState,rechargeState,cu_id) VALUES(?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, meterS)
	# ON DUPLICATE KEY UPDATE (?)

	return cur.lastrowid
# ------------------------------------------------------------------------------------ #
def update_meterStatus(conn, cu):
	"""
	update meterStatus
	:param conn:
	:param meter:
	:return: meter id
	"""
	sql = ''' UPDATE meterStatus
              SET meterID = ? ,
                  socketID = ?,
                  meterState = ? ,
                  rechargeState = ?,
                  cu_id = ? 
              WHERE meterID = ?'''
	cur = conn.cursor()
	cur.execute(sql, cu)


# ------------------------------------------------------------------------------------ #
def select_cuStatus_by_id(conn, id):
	"""
	Query cu by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM cuStatus WHERE cuCode=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT cuStatus by id: ["+ id + "]")

	# ADD labels and build up the JSON
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'cuStatus':jsonres}))

	return json.dumps({'cuStatus':jsonres})
# ------------------------------------------------------------------------------------ #
def select_meterStatus_by_id(conn, id):
	"""
	Query MeterStatus by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM meterStatus WHERE meterID=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT meterStatus by id: ["+ id + "]")

	# ADD labels and build up the JSON
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'meterStatus':jsonres}))

	return json.dumps({'meterStatus':jsonres})

# ------------------------------------------------------------------------------------ #
def join_Status(conn):
	"""
	JOIN MeterStatus and cuStatus
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT cuState,sn,cuCode,timestamp,meterID,socketID,meterState,rechargeState FROM cuStatus INNER JOIN meterStatus ON meterStatus.cu_id = cuStatus.cuCode")
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of JOIN Status")

	# ADD labels and build up the JSON
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'Status':jsonres}))

	return json.dumps({'Status':jsonres})

# ------------------------------------------------------------------------------------ #
def delete_cuStatus(conn, id):
	"""
	Delete a cuStatus by cu id
	:param conn: Connection to the SQLite database
	:param id: id of the cu
	:return:
	"""
	sql = 'DELETE FROM cuStatus WHERE cuCode=?'
	cur = conn.cursor()
	cur.execute(sql, (id,))

# ------------------------------------------------------------------------------------ #
def delete_meterStatus(conn, id):
	"""
	Delete a meterStatus by CU id
	:param conn: Connection to the SQLite database
	:param id: id of the MAIN CU
	:return:
	"""
	sql = 'DELETE FROM meterStatus WHERE cu_id=?'
	cur = conn.cursor()
	cur.execute(sql, (id,))

# ------------------------------------------------------------------------------------ #


# ------------------------------------------------------------------------------------ #
# CHARGING UNITS
# Methods for dedicated SQL purposes:
# ------------------------------------------------------------------------------------ #
def create_cu(conn, cu):
	"""
	Create a new CU into the cu table
	:param conn:
	:param cu:
	:return: cu id
	"""
	sql = ''' INSERT INTO cu(sn,cuCd,cuBrandId,cuModelId,cuName,v2gEnabled,maxVoltage,maxPower,coordX,coordY) VALUES(?,?,?,?,?,?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, cu)

	return cur.lastrowid
# ------------------------------------------------------------------------------------ #
def update_cu(conn, cu):
	"""
	update cu
	:param conn:
	:param cu:
	:return: cu id
	"""
	sql = ''' UPDATE cu
              SET sn = ? ,
                  cuCd = ?,
                  cuBrandId = ? ,
                  cuModelId = ? ,
                  cuName = ? ,
                  v2gEnabled = ? ,
                  maxVoltage = ? ,
                  maxPower = ? ,
                  coordX = ? ,
                  coordY = ? 
              WHERE cuCd = ?'''
	cur = conn.cursor()
	cur.execute(sql, cu)
# ------------------------------------------------------------------------------------ #
def delete_cu(conn, id):
	"""
	Delete a cu by cu id
	:param conn:  Connection to the SQLite database
	:param id: id of the cu
	:return:
	"""
	sql = 'DELETE FROM cu WHERE cuCd=?'
	cur = conn.cursor()
	cur.execute(sql, (id,))

# ------------------------------------------------------------------------------------ #
def select_all_cu(conn):
	"""
	Query all rows in the cu table
	:param conn: the Connection object
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM cu")

	rows = cur.fetchall()

	jsonres = []
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT all CU: ")

	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json (wrong approach):
	# for row in rows:
	#	for key in cur.description:
	#		jsonres.append({key[0]: value for value in row})
	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'cuList':jsonres}))

	return json.dumps({'cuList':jsonres})

# ------------------------------------------------------------------------------------ #
def select_cu_by_id(conn, id):
	"""
	Query cu by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM cu WHERE cuCd=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT CU by id: ["+ id + "]")

	# ADD labels and build up the JSON
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'cu':jsonres}))

	return json.dumps({'cu':jsonres})

# ------------------------------------------------------------------------------------ #
def create_meter(conn, meter):
	"""
	Create a new meter into the Meters table
	:param conn:
	:param meter:
	:return: meter id
	"""
	sql = ''' INSERT INTO meters(meterCode,meterCuId,pod,meterType,cu_id) VALUES(?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, meter)

	return cur.lastrowid
# ------------------------------------------------------------------------------------ #
def update_meter(conn, meter):
	"""
	update meter
	:param conn:
	:param meter:
	:return: meter id
	"""
	sql = ''' UPDATE meters
              SET meterCode = ? ,
                  meterCuId = ?	,
                  pod = ? ,
                  meterType = ? ,
		  cu_id = ?
              WHERE meterCuId = ?'''
	cur = conn.cursor()
	cur.execute(sql, meter)
# ------------------------------------------------------------------------------------ #
def delete_meter(conn, id):
	"""
	Delete a meters by cu id
	:param conn:  Connection to the SQLite database
	:param id: id of the meter
	:return:
	"""
	sql = 'DELETE FROM meters WHERE meterCuId=?'
	cur = conn.cursor()
	cur.execute(sql, (id,))

# ------------------------------------------------------------------------------------ #
def select_all_meter(conn):
	"""
	Query all rows in the meter table
	:param conn: the Connection object
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM meters")

	rows = cur.fetchall()
	
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT all meter: ")

	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'meterList':jsonres}))

	return json.dumps({'meterList':jsonres})

# ------------------------------------------------------------------------------------ #
def select_meter_by_id(conn, id):
	"""
	Query meter by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM meters WHERE meterCuId=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT meter by meterCuId: ["+ id + "]")

	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'meter':jsonres}))

	return json.dumps({'meter':jsonres})

# ------------------------------------------------------------------------------------ #
def create_plug(conn, plug):
	"""
	Create a new plug into the plugs table
	:param conn:
	:param project:
	:return: project id
	"""
	sql = ''' INSERT INTO plugs(plugId,socketType,connectorType,iMin,iMax,pMin,pMax,meter_id) VALUES(?,?,?,?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, plug)
	return cur.lastrowid
# ------------------------------------------------------------------------------------ #
def update_plug(conn, plug):
	"""
	update meter
	:param conn:
	:param meter:
	:return: meter id
	"""
	sql = ''' UPDATE plugs
              SET plugId = ?,
                  socketType = ? ,
                  connectorType = ? ,
                  iMin = ? ,
                  iMax = ? ,
                  pMin = ? ,
                  pMax = ? ,
		  meter_id = ?
              WHERE plugId = ?'''
	cur = conn.cursor()
	cur.execute(sql, plug)
# ------------------------------------------------------------------------------------ #
def delete_plug(conn, id):
	"""
	Delete a plug by plug id
	:param conn:  Connection to the SQLite database
	:param id: id of the plug
	:return:
	"""
	sql = 'DELETE FROM plugs WHERE plugId=?'
	cur = conn.cursor()
	cur.execute(sql, (id,))
# ------------------------------------------------------------------------------------ #
def select_all_plug(conn):
	"""
	Query all rows in the plugs table
	:param conn: the Connection object
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM plugs")

	rows = cur.fetchall()
	
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT all plug: ")

	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'plugList':jsonres}))

	return json.dumps({'plugList':jsonres})

# ------------------------------------------------------------------------------------ #
def select_plug_by_id(conn, id):
	"""
	Query plug by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM plugs WHERE plugId=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT plug by id: ["+ id + "]")

	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'plug':jsonres}))

	return json.dumps({'plug':jsonres})
# ------------------------------------------------------------------------------------ #
# SESSIONS MANAGEMENT:
# ------------------------------------------------------------------------------------ #
# ------------------------------------------------------------------------------------ #
# DEBUGGING PURPOSES (Remove previously stored sessions information):
# ------------------------------------------------------------------------------------ #
def delete_allCU(conn):
	"""
	Delete all CU related info
	:param conn: Connection to the SQLite database
	:return:
	"""
	sql = 'DELETE FROM meterStatus'
	cur = conn.cursor()
	cur.execute(sql)

	sql = 'DELETE FROM cuStatus'
	cur = conn.cursor()
	cur.execute(sql)

	sql = 'DELETE FROM cu'
	cur = conn.cursor()
	cur.execute(sql)

	sql = 'DELETE FROM meters'
	cur = conn.cursor()
	cur.execute(sql)

	sql = 'DELETE FROM plugs'
	cur = conn.cursor()
	cur.execute(sql)

	description = "[EconomicServer] Removed ALL CU information stored"
	if(enablePrints == True):
		print(str(description))

	return str(description)

def delete_allSessions(conn):
	"""
	Delete all sessions info
	:param conn: Connection to the SQLite database
	:return:
	"""
	sql = 'DELETE FROM sessionstart'
	cur = conn.cursor()
	cur.execute(sql)

	sql = 'DELETE FROM sessionend'
	cur = conn.cursor()
	cur.execute(sql)

	sql = 'DELETE FROM sessionupdate'
	cur = conn.cursor()
	cur.execute(sql)

	description = "[EconomicServer] Removed ALL session stored"
	if(enablePrints == True):
		print(str(description))

	return str(description)

# ------------------------------------------------------------------------------------ #
def add_NewSession(conn,session):
	"""
	Create a new Start session into the sessionstart table
	"""
	sql = ''' INSERT INTO sessionstart(cuCode,sessionID,meterID,plugId,smart,startSOC,endSOC,totalEnergy,millsToRecEnd,rechargeState,meterState,timestamp) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, session)

	return cur.lastrowid

# ------------------------------------------------------------------------------------ #
def select_all_startSession(conn):
	"""
	Query all rows in the sessionstart table
	:param conn: the Connection object
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM sessionstart")

	rows = cur.fetchall()

	jsonres = []
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT all Session Start: ")

	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json (wrong approach):
	# for row in rows:
	#	for key in cur.description:
	#		jsonres.append({key[0]: value for value in row})
	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'startSession':jsonres}))

	return json.dumps({'startSession':jsonres})

# ------------------------------------------------------------------------------------ #
def select_startSession_by_id(conn, id):
	"""
	Query sessionstart by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM sessionstart WHERE sessionID=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT CU by id: ["+ id + "]")

	# ADD labels and build up the JSON
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'Started':jsonres}))

	return json.dumps({'Started':jsonres})

# ------------------------------------------------------------------------------------ #
def add_UpdateSession(conn,session):
	"""
	Create a new Update session into the sessionupdate table
	"""
	sql = ''' INSERT INTO sessionupdate(cuCode,meterID,plugId,sessionID,timestamp,power,energy,current,voltage,DCcurrent,DCvoltage,totalEnergy,rechargeState,meterState) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, session)

	return cur.lastrowid

# ------------------------------------------------------------------------------------ #
def select_all_updateSession(conn):
	"""
	Query all rows in the sessionupdate table
	:param conn: the Connection object
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM sessionupdate")

	rows = cur.fetchall()

	jsonres = []
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT all Session Update: ")

	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json (wrong approach):
	# for row in rows:
	#	for key in cur.description:
	#		jsonres.append({key[0]: value for value in row})
	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'updateSession':jsonres}))

	return json.dumps({'updateSession':jsonres})
# ------------------------------------------------------------------------------------ #
def add_EndSession(conn,session):
	"""
	Create a new End session into the sessionend table
	"""
	sql = ''' INSERT INTO sessionend(cuCode,meterID,plugId,sessionID,timestamp,power,energy,current,voltage,DCcurrent,DCvoltage,totalEnergy,rechargeState,meterState) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) '''
	cur = conn.cursor()
	cur.execute(sql, session)

	return cur.lastrowid
# ------------------------------------------------------------------------------------ #
def select_all_endSession(conn):
	"""
	Query all rows in the sessionend table
	:param conn: the Connection object
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM sessionend")

	rows = cur.fetchall()

	jsonres = []
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT all Session End: ")

	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json (wrong approach):
	# for row in rows:
	#	for key in cur.description:
	#		jsonres.append({key[0]: value for value in row})
	# ---------------------------------------------------------------- # 
	# ADD labels and build up the json
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'endSession':jsonres}))

	return json.dumps({'endSession':jsonres})
# ------------------------------------------------------------------------------------ #
def select_endSession_by_id(conn, id):
	"""
	Query sessionend by id
	:param conn: the Connection object
	:param id:
	:return:
	"""
	cur = conn.cursor()
	cur.execute("SELECT * FROM sessionend WHERE sessionID=?", (id,))
	
	rows = cur.fetchall()
	 
	if(enablePrints == True):
		print("[EconomicServer] Result of SELECT Session End by id: ["+ id + "]")

	# ADD labels and build up the JSON
	jsonres = [dict(zip([key[0] for key in cur.description], row)) for row in rows]

	if(enablePrints == True):
		print(json.dumps({'Ended':jsonres}))

	return json.dumps({'Ended':jsonres})


if(localDebugDocker == True):
	broker       = "10.8.0.50"
else:
	broker       = "databroker"

broker_port  = 8883
USER_NAME    = "fronius-fur"
PASSWORD     = "r>U@U7J8xZ+fu_vq"
# ------------------------------------------------------------------ #
if(localDebug == True):
	MQTT_TLS     = "./tls/s4g-ca.crt"	
else:
	MQTT_TLS     = "/srv/flask_app/tls/s4g-ca.crt"

profevTopic  = "EV/Data"
# ------------------------------------------------------------------ #


def on_data_disconnect(client, userdata, rc):
	global mqtt_pub
	global enablePrints
	global MQTT_pub_disconnected

	if(enablePrints == True):
		print("[EconomicServer][MQTT-GLOBAL][INFO] Publisher disconnected, going to stop the loop")

	mqtt_pub.loop_stop()

	MQTT_pub_disconnected = True

# ------------------------------------------------------------------------------------ #
def startGlobalPublisher():
	global broker
	global broker_port
	global mqtt_pub
	global MQTT_TLS
	global USER_NAME
	global PASSWORD
	global enablePrints
	global MQTT_pub_disconnected
	global devScenario

	# Client-ID as parameter (?) 
	# Multiple instances (be careful)
	mqtt_pub =  mqtt.Client()

	MQTT_pub_disconnected = True

	while MQTT_pub_disconnected:
		try:
			if(enablePrints == True):
				print("[EconomicServer][MQTT-GLOBAL][INFO] Building the GLOBAL PUBLISHER (mqtt-client)")

			if(devScenario != True):
				if(enablePrints == True):
					print("[EconomicServer][MQTT-GLOBAL][INFO] Building with following property: ")
					print("[EconomicServer][MQTT-GLOBAL][INFO][MQTT_TLS]: " + str(MQTT_TLS))
					print("[EconomicServer][MQTT-GLOBAL][INFO][USER_NAME]: " + str(USER_NAME))
					print("[EconomicServer][MQTT-GLOBAL][INFO][PASSWORD]: " + str(PASSWORD))

				mqtt_pub.tls_set(MQTT_TLS)
				mqtt_pub.tls_insecure_set(True)
				mqtt_pub.username_pw_set(username=USER_NAME,password=PASSWORD)

			mqtt_pub.on_disconnect = on_data_disconnect

			if(enablePrints == True):			
				print("[EconomicServer][MQTT-GLOBAL][INFO] Publisher Connecting...")
				print("[EconomicServer][MQTT-GLOBAL][INFO] " + str(broker) + ":" + str(broker_port))

			if(mqtt_pub.connect(broker, int(broker_port), 60) == 0):
				MQTT_pub_disconnected = False
				
			if(enablePrints == True):			
				print("[EconomicServer][MQTT-GLOBAL][INFO] Publisher Connected...")

		except Exception as e:
			print("[EconomicServer][MQTT-GLOBAL][INFO] Publisher Stopped %s" %e)
			MQTT_pub_disconnected = True
			time.sleep(1)

	mqtt_pub.loop_start()

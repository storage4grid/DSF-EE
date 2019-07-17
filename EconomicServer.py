#!/usr/bin/env python
'''
* ------------------------------------------------------------------------------------------------- *
* !!!WARNING ABOUT DEVELOPMENT!!!
* ------------------------------------------------------------------------------------------------- *
* When the current software is run by uWSGI the main() is not executed! 
* This is because the uWSGI load balancer trigger directly the flask APIs!
* Then, it is important to remember that by exploiting its multi-process management,
* there will be multiple instances running!
* Consequently, a configuration phase (i.e. mqtt client setup),
* it will affect only the current active process!
* In order to manage properly each instance, it is mandatory, 
* to control the initialization of every component on every API callback.
*
* ------------------------------------------------------------------------------------------------- *
* !!!WARNING ABOUT DEPLOYMENT!!!
* ------------------------------------------------------------------------------------------------- *
* Remember that, by building the new docker image you will override the persistence SQlite Database!
* In order to mantains the previously stored data, before compiling it again, you have to manually:
* Copy from the dedicated volume the updated Database on the EconomicServer folder
* (Overriding the starting one)
* Then you can safely re-build and re-start it.
*
* ------------------------------------------------------------------------------------------------- *
* !!!UPDATES!!!
* ------------------------------------------------------------------------------------------------- *
* Fixed API endpoints
*
* ------------------------------------------------------------------------------------------------- *
* !!! BUILD INSTRUCTIONS !!!
* ------------------------------------------------------------------------------------------------- *
* sudo docker build . -t economicserverimage
*
* BASE (No MQTT support due to databroker embedded inside docker fs of the same host):
* sudo docker run --name economicserver -p 9082:9081 -d economicserverimage
*
* ADVANCED (attach to the already present network and link to mosquitto to enable MQTT communication):
* sudo docker run --name economicserver --network=12_default --link mqtt:databroker -p 9082:9081 -d economicserverimage
*
* CERTIFICATES GENERATION (CN value must be the same as for the FDQN)
* sudo openssl req -x509 -nodes -days 565 -newkey rsa:2048 -keyout /etc/ssl/private/nginx-selfsigned.key -out /etc/ssl/certs/nginx-selfsigned.crt
* 
* ------------------------------------------------------------------------------------------------- *
* !!! DEBUG INSTRUCTIONS !!!
* ------------------------------------------------------------------------------------------------- *
* Show certificate property
* curl -k -v https://dwh.storage4grid.eu:9082/
* curl --insecure -v https://www.google.com 2>&1 | awk 'BEGIN { cert=0 } /^\* Server certificate:/ { cert=1 } /^\*/ { if (cert) print }'
* curl --cacert mycompany.cert  https://www.mycompany.com
* ------------------------------------------------------------------------------------------------- *
* !!! DETAILS !!!
* ---------------------------------------------------------------------------------------------------------------
* Simple REST server for Python (3). Built to be multithreaded together with nginx and uwsgi.
* ---------------------------------------------------------------------------------------------------------------
* @Version 0.0.1
*                                           Storage4Grid EU Project
*                                      Implementation of Economic Server Connector
*                                          on server 130.192.86.144
* @Notes:
* ---------------------------------------------------------------------------------------------------------------
* The current Backend will interact with Professional GUI and with the DSF-SE to:
* - receive Professional GUI and DSF-SE inputs.
* - evaluate the economic model scenario.
* - store persistently the information of interest. JSON File for debug and DB: sqlite3
* - forward the economic results back to the Professional GUI
* ---------------------------------------------------------------------------------------------------------------
* It is built in the following context:
* - Public IP                 
* - HTTPS only APIs          (nginx settings)
* - self-signed certificates (openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365)
* ---------------------------------------------------------------------------------------------------------------
* In order to satisfy the security requirements to prevent cyber-attacks,
* it has been built in python exploiting Flask together with:
* - nginx
* - uwsgi
* ---------------------------------------------------------------------------------------------------------------
* It is installed as a systemctl service.
* It is run with the following base-settings:
* # uwsgi --http-socket :9090 --plugin python --wsgi-file foobar.py
* It is run with the following good-settings:
* # uwsgi --http-socket :9090 --plugin python --wsgi-file foobar.py
* It is run with the following best-settings (exploting a configuration file):
* # uwsgi --ini myproject.ini
* ---------------------------------------------------------------------------------------------------------------
* @OtherNotes:
* If you want to run Flask in production, 
* be sure to use a production-ready web server like Nginx, 
* and let your app be handled by a WSGI application server like Gunicorn/uWSGI.
* https://uwsgi-docs.readthedocs.io/en/latest/WSGIquickstart.html
* https://www.digitalocean.com/community/tutorials/how-to-serve-flask-applications-with-uswgi-and-nginx-on-ubuntu-18-04
* ---------------------------------------------------------------------------------------------------------------
* @Features exposed towards Professional GUI & DSF-SE:
* -POST- https://dwh.storage4grid.eu:9082/EE/input
* ---------------------------------------------------------------------------------------------------------------
* Following APIs are all REST GET:
* TESTING PURPOSES:
* - https://10.8.0.50:9082/
* ---------------------------------------------------------------------------------------------------------------
* @Author: Ligios Michele
* @Created: 2019-06-11
* @Updated: 2019-07-17
'''
# ------------------------------------------------------------------------------------ #
# Generic Libraries:
import sys, os, re, shutil, json
# ------------------------------------------------------------------------------------ #
from flask import Flask, request
# ------------------------------------------------------------------------------------ #
import configparser
import time
import sqlite3

import datetime

# ------------------------------------------------------------------------------------ #
import paho.mqtt.client as mqtt
# ------------------------------------------------------------------------------------ #
# Import libraries in lib directory
base_path = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(base_path, 'lib'))
# ------------------------------------------------------------------------------------ #
# ------------------------------------------------------------------------------------ #
# * Serving Flask app "EconomicServer" (lazy loading)
# * Environment: production
#   WARNING: Do not use the development server in a production environment.
#   Use a production WSGI server instead.
# * Debug mode: on
# * Running on http://127.0.0.1:5000/ (Press CTRL+C to quit)
# * Restarting with stat
# ------------------------------------------------------------------------------------ #
app = Flask(__name__)
# ------------------------------------------------------------------------------------ #
# TODO: VERIFY VERY WELL THE FOLLOWING FLAGS BEFORE BUILDING!
localDebugHTTP   = True         # Required for building local python app (not inside docker) in HTTP or HTTPS
# ------------------------------------------------------------------------------------ #
enablePrints     = True
enableFullPrints = False
enableFulldebug  = False
# ------------------------------------------------------------------------------------ #
@app.route("/")
def home():
	return "Economic Server Reached!"
# ------------------------------------------------------------------------------------ #
# FIXED PARAMETERS (Previously evaluated):
# ------------------------------------------------------------------------------------ #
# Prudent average rate for decreasing  battery price (%):
prudentAverageBatteries = -7.16/100
# ------------------------------------------------------------------------------------ #
# Regression parameters:
a0 = 24.426
a1 = 2994.1
a2 = -90.806
a3 = 0.8923
a4 = -0.0027
# ------------------------------------------------------------------------------------ #
# Rescaled Regression parameters:
b0 = a0 - 7000
b1 = a1
b2 = a2
# ------------------------------------------------------------------------------------ #
# Range of allowded values for kwp (required to define the PV penetration %):
KWpMax = 150
Econsumption = [2500,1200,2500,800]
# ------------------------------------------------------------------------------------ #
# These values Must be shared among the Scenarios:
# Percentage of shared Power Loss (50%)
pSharedPLoss = 0.5
# R Percentage (7%): 
r = 0.07
# Power en:
Pen = 0.31
# Number of Households:
nhouse = 15
# Fixed cost amount (Scenario1):
fixed_cost = 9000

# ------------------------------------------------------------------------------------ #
# Allowed Scenario: [0,1,2,3]
scenarioDescription = ["Grid Strenghtening",\
			"Decentralized Storage at houhold level",\
			"Centralized Storage at Sub-station level",\
			"Both centralized and decentralized storage"]
# ------------------------------------------------------------------------------------ #
kwp     = 0
pLoss   = 0
nss     = 0
CPwLoss = 0
# ------------------------------------------------------------------------------------ #
#  YEAR  | SIMULATED DATA (DOLLARS) |  SIMULATED DATA (EURO) 
simulatedBatteryData = [[2014,1331,1185],\
			[2015,1236,1100],\
			[2016,1147,1021],\
			[2017,1065,948],\
			[2018,989,880],\
			[2019,918,817],\
			[2020,852,758],\
			[2021,791,704],\
			[2022,734,654],\
			[2023,682,607],\
			[2024,633,563],\
			[2025,588,523],\
			[2026,546,486],\
			[2027,507,451],\
			[2028,470,419],\
			[2029,437,389],\
			[2030,405,361]]

# ------------------------------------------------------------------------------------ #
# Example of Message (Scenario 0):
# {
#  "Simulation": 0,
#  "Type": "oneShot",
#  "Info":
#   {
#     "SimulationTime": 10,
#     "kwp": 100,
#     "PLoss": 20,
#     "Nss": 0,
#     "BatteryList":
#     [      
#     ]
#   }
# }
# ------------------------------------------------------------------------------------ #
# Example of Message (Scenario 1):
# {
#  Simulation: 1,
#  Type: "oneShot",
#  Info:
#   {
#     SimulationTime: 10,
#     kwp: 100,
#     PLoss: 20,
#     Nss: 1000,
#     BatteryList:
#     [
#       {
#         BatteryID: "A",
#         Capacity:  10,
#         LifeTime:  20,
#         Position:  "Residential"
#       },
#       {
#         BatteryID: "B",
#         Capacity:  80,
#         LifeTime:  30,
#         Position:  "SubStation"
#       }
#     ]
#   }
# }
# ------------------------------------------------------------------------------------ #
@app.route("/EE/input",methods=['POST'])
def startEconomicEvaluation():
	# ----------------------------------- #
	DSO_CF      = []
	DSO_PV      = []
	PROSUMER_CF = []
	PROSUMER_PV = []
	timeArray   = []
	batteryList = []
	# ----------------------------------- #
	residential_EssCapacity = 0
	residential_EssLifetime = 0
	dso_EssCapacity = 0
	dso_EssLifetime = 0
	# ----------------------------------- #
	description = "[EconomicServer][HTTPS][POST] Economic Model Evaluation"
	if(enablePrints == True):
		print(str(description))
	# ----------------------------------- #
	# Receive and parse
	try:					
		req_data      = request.get_json() 

		if(enableFulldebug == True):
			timestr = time.strftime("%Y%m%d-%H%M%S")
			# -------------------------------------------------------------------------------------------------- #
			# IMPROVED DEBUG:
			# Verify if already exists (should not because time in current date)
			# In case of fast request (more than one per second) it will overwrite the file.
			# -------------------------------------------------------------------------------------------------- #
			pathFile = "./startEEJsonDebug"+str(timestr)+str(debugExtension)
			exists = os.path.isfile(pathFile)
			counter = 0
			while exists:
				counter +=1				
				# Store configuration file values
				pathFile = "./startEEJsonDebug"+str(timestr)+"_"+str(counter)+str(debugExtension)
				exists = os.path.isfile(pathFile)
			# -------------------------------------------------------------------------------------------------- #
			with open(pathFile, 'w') as outfile:  
				json.dump(req_data, outfile)

		# -------------------------------------------------------------------------------------------------- #
		idSimulation        = req_data['simulation_id']
		locationSimulation  = req_data['grid_name']
		# ---------------------------------------------------------- #
		simulationTime      = req_data['simulation_time']
		# ---------------------------------------------------------- #
		kwp                 = req_data['kwp']
		pLoss               = req_data['kwh_losses']
		batteryList         = req_data['ESS_info']
		# ---------------------------------------------------------- #
		# FURTHER CONTROLS ABOUT GIVEN INPUTS:
		# ---------------------------------------------------------- #
		# Numerical Input validation:
		# ---------------------------------------------------------- #
		if(isinstance(batteryList, list) != True):
			raise ValueError('Wrong Input! ESS_info must be a list!')			
		nss                 = len(batteryList) 
		if(isinstance(kwp, (int, float, complex)) != True):
			raise ValueError('Wrong Input! kwp must be a number!')			
		if(isinstance(simulationTime, (int, float, complex)) != True):
			raise ValueError('Wrong Input! simulationTime must be a number!')			
		if(isinstance(pLoss, (int, float, complex)) != True):
			raise ValueError('Wrong Input! kwh_losses must be a number!')			
		if(isinstance(nss, (int, float, complex)) != True):
			raise ValueError('Wrong Input! inherited number of ESS must be a number!')			

		# ---------------------------------------------------------- #
		# Need to calculate the PV penetration % (from kwp):
		pvPerc = (kwp/KWpMax)
		if(enableFullPrints == True):
			print("Request Received: content("+str(req_data) + ")")
			print("idSimulation: " + str(idSimulation))
			print("kwp    = "+str(kwp))
			print("pvPerc = "+str(pvPerc*100) + " %")

		# ---------------------------------------------------------- #
		# IF the INPUT will involve pvPerc instead of kwp
		# Then enable the following lines:
		# pvPerc         = infoSimulation['PVperc']
		# Need to calculate the kwp starting from the PV penetration %:
		# kwp = pvPerc*KWpMax
		# ---------------------------------------------------------- #
		# Analize the Given Batteries List to identify the Scenario:
		foundResidential = False
		foundSubstation  = False

		resCounter = 0
		dsoCounter = 0

		avg_res_EssCapacity = 0
		avg_res_EssLifetime = 0

		avg_dso_EssCapacity = 0
		avg_dso_EssLifetime = 0
		# ---------------------------------------------------------- #
		i = 0
		while( i < len(batteryList)):
			if(batteryList[i]['location'] == "household"):
				foundResidential = True

				residential_EssCapacity = batteryList[i]['kwh']
				residential_EssLifetime = batteryList[i]['lifetime']

				avg_res_EssCapacity += residential_EssCapacity
				avg_res_EssLifetime += residential_EssLifetime
				resCounter += 1

			elif(batteryList[i]['location'] == "substation"):
				foundSubstation  = True

				dso_EssCapacity = batteryList[i]['kwh']
				dso_EssLifetime = batteryList[i]['lifetime']

				avg_dso_EssCapacity += dso_EssCapacity
				avg_dso_EssLifetime += dso_EssLifetime
				dsoCounter += 1

			i += 1

		ScenarioID = -1

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer] S4G Service [Input] Error %s" %e)
		return str("[EconomicServer] S4G Service [Input] Error %s" %e)

	try:
		# ---------------------------------------------------------- #
		# Scenario 0: NumberESS = 0 and Nss = 0
		# Scenario 1: NumberESS > 0 and Nss > 0 and Position = Residential only
		# Scenario 2: NumberESS > 0 and Nss > 0 and Position = Substation only
		# Scenario 3: NumberESS > 0 and Nss > 0 and Position = Both
		# ---------------------------------------------------------- #
		now = datetime.datetime.now()
		year = now.year

		if(len(batteryList) == 0 and nss == 0):
			ScenarioID = 0
		elif(len(batteryList) > 0 and nss > 0):
			# Requried to find the proper row of BatteryCosts Structure:
			now = datetime.datetime.now()
			year = now.year

			if(enableFullPrints == True):
				print("simulatedBatteryData: ")
				print(simulatedBatteryData)

			# Extract the estimation built about the current year:
			elementRow = [x for x in simulatedBatteryData if x[0] == year]

			# Extract the proper value:
			battSimulCost = elementRow[0][2]
			if(enableFullPrints == True):
				print("BatterySimluatedCost: " +str(battSimulCost))

			if(foundResidential == True and foundSubstation == False):
				ScenarioID = 1
				# ------------------------------------------------------------- #
				avg_res_EssCapacity = avg_res_EssCapacity/resCounter
				avg_res_EssLifetime = avg_res_EssLifetime/resCounter
				residential_capexSize = battSimulCost*avg_res_EssCapacity
				# ------------------------------------------------------------- #
			elif(foundResidential == False and foundSubstation == True):
				ScenarioID = 2
				# ------------------------------------------------------------- #
				avg_dso_EssCapacity = avg_dso_EssCapacity/dsoCounter
				avg_dso_EssLifetime = avg_dso_EssLifetime/dsoCounter
				dso_capexSize = battSimulCost*avg_dso_EssCapacity
				# ------------------------------------------------------------- #
			elif(foundResidential == True and foundSubstation == True):
				ScenarioID = 3
				# ------------------------------------------------------------- #
				avg_res_EssCapacity = avg_res_EssCapacity/resCounter
				avg_res_EssLifetime = avg_res_EssLifetime/resCounter
				avg_dso_EssCapacity = avg_dso_EssCapacity/dsoCounter
				avg_dso_EssLifetime = avg_dso_EssLifetime/dsoCounter
				# ------------------------------------------------------------- #
				residential_capexSize = battSimulCost*avg_res_EssCapacity
				dso_capexSize         = battSimulCost*avg_dso_EssCapacity
				# ------------------------------------------------------------- #
			else:
				if(enablePrints == True):
					print("[EconomicServer] S4G Service [Starting Simulation] Error")
				return str("[EconomicServer] S4G Service [Starting Simulation] Error (" + str(req_data) + ")")
		else:
			# --------------------------------------- #
			# It means:
			# (len(batteryList) < 0) or 
			# (len(batteryList) == 0 and nss > 0) or
			# (len(batteryList) == 0 and nss < 0) or
			# (len(batteryList)  > 0 and nss < 0)
			# All these combinations are not allowed!
			# --------------------------------------- #
			if(enablePrints == True):
				print("[EconomicServer] S4G Service [Starting Simulation] Input Parsing Error")
			return str("[EconomicServer] S4G Service [Starting Simulation] Input Parsing Error (" + str(req_data) + ")")

		if(enablePrints == True):
			print("[EconomicServer] Identified Scenario: " +str(ScenarioID))

		if(enableFullPrints == True):
			print("[EconomicServer] GS (Parameters): ")
			print("[EconomicServer] a0: " + str(a0))
			print("[EconomicServer] a1: " + str(a1))
			print("[EconomicServer] a2: " + str(a2))
			print("[EconomicServer] a3: " + str(a3))
			print("[EconomicServer] a4: " + str(a4))
			print("[EconomicServer] Steps Formula: ")
			print("[EconomicServer] [a4*((kwp)^4]=" + str(a4*((kwp)**4)))
			print("[EconomicServer] [a3*((kwp)^3)]=" + str(a3*((kwp)**3)))
			print("[EconomicServer] [a2*((kwp)^2)]=" + str(a2*((kwp)**2)))
			print("[EconomicServer] [a1*(kwp)]=" + str(a1*(kwp)))

		# ---------------------------------------------------------- #
		# Need to calculate the Grid Sthreghtening:
		gs  = a0 + a1*(kwp) + a2*((kwp)**2) + a3*((kwp)**3) + a4*((kwp)**4) 

		# Need to calculate the Grid Sthrenghtening Equivalent:
		gse = b0 + b1*(kwp) + b2*((kwp)**2)

		if(enableFullPrints == True):
			print("[EconomicServer] GS: " +str(gs))
			print("[EconomicServer] GSE: " +str(gse))

		# Directly related to the Grid Strenghtening values just built:
		CAPEX = gs
		OPEX  = 0.02*CAPEX

		# ---------------------------------------------------------- #
		EconsumptionCost = Econsumption[ScenarioID] * Pen
		CPwLoss = Pen * pLoss

		if(enableFullPrints == True):
			print("[EconomicServer] CAPEX: " +str(CAPEX))
			print("[EconomicServer] OPEX: " +str(OPEX))
			print("[EconomicServer] Pen: " + str(Pen))
			print("[EconomicServer] PLoss: " + str(pLoss))
			print("[EconomicServer] EconsumptionCost: " +str(EconsumptionCost))
			print("[EconomicServer] CPwLoss: " +str(CPwLoss))

		# ---------------------------------------------------------- #
		# Common values for each Scenario built until now:
		# ---------------------------------------------------------- #
		EconsumptionCostScenario0 = Econsumption[0] * Pen

		# ---------------------------------------------------------- #
		# Now it is required to build up the Tables
		# Remember that some column are specific for each Scenario
		# ---------------------------------------------------------- #
		timeArray = [i for i in range(simulationTime+1)]
		if(ScenarioID == 0):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 0 Evaluation")

			for x in timeArray:
				if(x == 0):
					DSO_CF.append(CAPEX + CPwLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))
					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(CAPEX + CPwLoss))
						print("DSO_PV["+str(x)+"]="+str(DSO_CF[x]/((1+r)**(x))))

					if(DSO_CF[x] == 0): 
						PROSUMER_CF.append(0)
						PROSUMER_PV.append(0)
					else:
						PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost * nhouse)
						PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))
				else:

					DSO_CF.append(OPEX + CPwLoss * pSharedPLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(OPEX + CPwLoss * pSharedPLoss))
						print("DSO_PV["+str(x)+"]="+str(DSO_CF[x]/((1+r)**(x))))

					if(DSO_CF[x] == 0): 
						PROSUMER_CF.append(0)
						PROSUMER_PV.append(0)
					else:
						PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCost * nhouse)
						PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))
  
		elif(ScenarioID == 1):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 1 Evaluation")
			# ---------------------------------------------------------- #
			# (ESS Capacity)  KWh_ess  = 12
			# (ESS LifeTime)  K - time = 15
			# ---------------------------------------------------------- #
			for x in timeArray:
				if(x == 0):
					DSO_CF.append(CAPEX + CPwLoss * pSharedPLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (nss * EconsumptionCost) + ( nhouse - nss ) * (EconsumptionCostScenario0)
					
					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

				else:
					DSO_CF.append(OPEX + CPwLoss)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					if((x % avg_res_EssLifetime) == 0):  
						tmpValue = (nss * residential_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (nss * EconsumptionCost) + ( nhouse - nss ) * (EconsumptionCostScenario0)
					else:
						tmpValue = CPwLoss * pSharedPLoss + nss * EconsumptionCost + (nhouse - nss) * EconsumptionCostScenario0

					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))
		# ---------------------------------------------------------- #
		elif(ScenarioID == 2):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 2 Evaluation")
			
			for x in timeArray:
				if(x == 0):
					tmpValue = (nss * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (CAPEX + OPEX)
					
					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCostScenario0 * nhouse)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

				else:
					if((x % avg_dso_EssLifetime) == 0):  
						tmpValue = (nss * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + (pSharedPLoss * CPwLoss) + (CAPEX + OPEX)
					else:
						tmpValue = (pSharedPLoss * CPwLoss) + (OPEX)

					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					PROSUMER_CF.append(CPwLoss * pSharedPLoss + EconsumptionCostScenario0 * nhouse)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))
		# ---------------------------------------------------------- #
		elif(ScenarioID == 3):
			if(enablePrints == True):
				print("[EconomicServer] Scenario 3 Evaluation")

			for x in timeArray:
				if(x == 0):
					# ------------------------------------------------------------------------------------ #
					tmpValue = (dsoCounter * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss*CPwLoss + (CAPEX + OPEX)
					# ------------------------------------------------------------------------------------ #
					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))

					# ------------------------------------------------------------------------------------ #
					tmpValue = (avg_res_EssLifetime * residential_capexSize * ( 1 + prudentAverageBatteries )**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
					# ------------------------------------------------------------------------------------ #
					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

					# ------------------------------------------------------------------------------------ #
				else:
					if((x % avg_dso_EssLifetime) == 0): 
						tmpValue = (dsoCounter * dso_capexSize * (1+prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss*CPwLoss + (CAPEX + OPEX)
					else:
						tmpValue = (pSharedPLoss * CPwLoss) + (OPEX)
					# ------------------------------------------------------------------------------------ #
					DSO_CF.append(tmpValue)
					DSO_PV.append(DSO_CF[x]/((1+r)**(x)))

					if(enableFullPrints == True):
						print("DSO_CF["+str(x)+"]="+str(DSO_CF[x]))
						print("DSO_PV["+str(x)+"]="+str(DSO_PV[x]))
					# ------------------------------------------------------------------------------------ #
					if((x % avg_res_EssLifetime) == 0): 
						tmpValue = (avg_res_EssLifetime * residential_capexSize * (1 + prudentAverageBatteries)**(x)) + fixed_cost + pSharedPLoss * CPwLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
					else:
						tmpValue = CPwLoss * pSharedPLoss + EconsumptionCost * resCounter + (nhouse - resCounter) * EconsumptionCostScenario0
					# ------------------------------------------------------------------------------------ #
					PROSUMER_CF.append(tmpValue)
					PROSUMER_PV.append(PROSUMER_CF[x] / ((1+r)**(x)))

					if(enableFullPrints == True):
						print("PROSUMER_CF["+str(x)+"]="+str(PROSUMER_CF[x]))
						print("PROSUMER_PV["+str(x)+"]="+str(PROSUMER_PV[x]))

	except Exception as e:
		if(enablePrints == True):
			print("[EconomicServer] S4G Service [Starting Economic Evaluation] Error %s" %e)
		return str("[EconomicServer] S4G Service [Starting Economic Evaluation] Error %s" %e)

	# -------------------- #
	TCO_DSO        = sum(DSO_PV)
	TCO_PROSUMER   = sum(PROSUMER_PV)
	TCO_AGGREGATED = TCO_PROSUMER - TCO_DSO
	# -------------------- #
	if(enablePrints == True):
		print("[EconomicServer] Identified Scenario: [" + str(ScenarioID) + "]")
		print("[EconomicServer] Identified Scenario: [" + str(scenarioDescription[ScenarioID]) + "]")
		print("[EconomicServer] TCO(DSO): " + str(TCO_DSO))
		print("[EconomicServer] TCO(AGGREGATED): " + str(TCO_AGGREGATED))
		print("[EconomicServer] TCO(PROSUMER): " + str(TCO_PROSUMER))

	# -------------------- #
	# Must Return a JSON:
	#{
	#"simulation_id":0,
	#"scenario_id":1,
	#"scenario_name":"AA",
	#"TCO_DSO":10,
	#"TCO_Aggregated":110,
	#"TCO_Community":90
	#}
	# -------------------- #
	result = {"simulation_id":idSimulation,"scenario_id":ScenarioID,"scenario_name":str(scenarioDescription[ScenarioID]),\
		 "TCO_DSO":TCO_DSO,"TCO_Aggregated":TCO_AGGREGATED,"TCO_Community":TCO_PROSUMER}
	# -------------------- #
	return json.dumps(result)

# ------------------------------------------------------------------------------------ #
# IF the current python application is triggered by uWSGI it means that 
# the following main() will never be executed!
# ------------------------------------------------------------------------------------ #
if __name__ == "__main__":
	print((sys.version_info))
	print("Storage4Grid EU Project: Implementation of EconomicServer Backend")
	print("[EconomicServer-Backend] Restoring back the Server configuration")
	print("[EconomicServer-Backend] Starting REST Server")
	if(localDebugHTTP == True):
		print("[EconomicServer-Backend] DEBUGGING MODE! ONLY FOR LOCAL PURPOSES!")
		app.run(host='0.0.0.0', port=9082) # HTTP
	else:
		print("[EconomicServer-Backend] PRODUCTION MODE!") # HTTPS
		app.run(ssl_context=('ssl/nginx-selfsigned.crt', 'ssl/nginx-selfsigned.key'), port=9082)

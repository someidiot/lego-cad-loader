#!/usr/bin/python

#
# Script: load_moc.py
#
# Usage: load_moc.py <path to file>
#
# This script will parse a CAD file of a LEGO model and retrieve a list of its 
# parts. It will print to stdout any important steps taken or warnings to the 
# user that require further investigation.
#
# Supports:
# - LXFML (uncompressed LXF file)
# - MPD
# - LDR
#
# Depends on:
# - ldraw.xml if processing an LXFML file
#
# Ldraw reference: http://www.ldraw.org/Article218.html
# Extensions eg LPub: http://www.ldraw.org/Article342.html
# LPub: https://sites.google.com/site/workingwithlpub/advanced-techniques/metacommands
# MLCad file format extensions: http://mlcad.lm-software.com/
# LDD reference: http://www.eurobricks.com/forum/index.php?showtopic=48239&st=0&p=850065&#entry850065
#

import sys
reload(sys)
sys.setdefaultencoding("utf-8")

import os
import re
#import psycopg2
import xml.etree.ElementTree as et # for LXFML parsing
import json
from io import open


if (len(sys.argv) > 1):
	FILE = sys.argv[1]
	#SET = sys.argv[2]
else:
	FILE = 'C:\\Projects\\Lego\\MOCs\\Nico\\GBBwave.ldr'
	#SET = ""

#print "Opening " + FILE

output_parts = list()
output_msg = list()

output_msg.append("Loading File")
try:
	f = open(FILE)
except Exception, e:
	print (e)
	sys.exit()

# Determine format of file
bytes = f.read(2)
if (bytes == "<?"):
	output_msg.append("Format: LDD")
	format = "LDD"
else:
	output_msg.append("Format: MPD")
	format = "MPD"
f.close()


def test_encoding(filename, code):
	# This is stupid
	f = open(filename, encoding=code)
	try:
		for line in f:
			continue
	except Exception, e:
		#print (e)
		return e
	return 0

	
	
if format == "LDD":
	
	# LEGO Digital Designer format
	# LXF is a zip file containing a PNG and LXFML xml file
	# This script assumes it is working on the LXFML file
	
	# First phase - read ldraw.xml and build list of part/color mappings
	
	color_map = {}
	part_map = {}
	decoration_map = {}
	# TODO: stop using this and just use mapping tables in calling program
	try:
		f = open(sys.path[0] + '/ldraw.xml')
	except Exception, e:
		output_msg.append(e)
		sys.exit()
	xml = f.read()
	#print "Read " + str(len(xml)) + " bytes"
	x_tree = et.fromstring(xml)
	output_msg.append("Using ldraw.xml: " + x_tree.attrib.get('comment'))
	for x_mat in x_tree.findall('Material'):
		ldraw = x_mat.attrib.get('ldraw')
		ldd = x_mat.attrib.get('lego')
		color_map[ldd] = ldraw
	for x_brick in x_tree.findall('Brick'):
		ldraw = x_brick.attrib.get('ldraw')
		ldd = x_brick.attrib.get('lego')
		part_map[ldd] = ldraw
	for x_brick in x_tree.findall('Decoration'):
		ldraw = x_brick.attrib.get('rb')
		ldd = x_brick.attrib.get('lego')
		decoration_map[ldd] = ldraw
	f.close()
	output_msg.append(" Color Maps: " + str(len(color_map)))
	output_msg.append(" Brick Maps: " + str(len(part_map)))
	output_msg.append(" Decoration Maps: " + str(len(decoration_map)))
	
	
	# Second phase - parse LXFML xml and build list of parts using ldraw.xml mappings where necessary
	
	f = open(FILE)
	xml = f.read()
	#print "Read " + str(len(xml)) + " bytes"
	final_parts = list()
	x_tree = et.fromstring(xml)
	x_bricks = x_tree.find('Bricks')
	for x_brick in x_bricks.findall('Brick'):
		# We use the part id's from the Brick entry, but the colors are in the Part entry.
		#part = x_brick.attrib.get('designID')
		#x_part = x_brick.find('Part')
		# There may be multiple parts if this is a composite part, so grab the lowest level.
		for x_part in x_brick.findall('Part'):
			part = x_part.attrib.get('designID')
			color = x_part.attrib.get('materials')
			color = color.split(",")[0] # in case there are multiple colors, just use the first one
			decoration = x_part.attrib.get('decoration')
			if (decoration):
				decoration = decoration.split(",")[0] # in case there are multiple colors, just use the first one
				#print "dec = " + decoration

			if color in color_map:
				color = color_map[color]
			#part = x_part.attrib.get('designID')
			
			if part in part_map:
				part = part_map[part]
				part = part.split(".")[0]

			if decoration in decoration_map:
				#print "found " + decoration
				part = decoration_map[decoration]

			final_parts.append(color + "|" + part)
	f.close()
	
	

elif format == "MPD":

	# MLCad format
	# This script can parse MPD or LDR files (barely... they suck even more than my ability
	# to write code to parse them).
	
	# Most files are in ASCII, but test it
	code = 'ascii'
	res = test_encoding(FILE, code)
	# If it fails, try other types that are sometimes used
	if (res != 0):
		code = 'utf-8'
		res = test_encoding(FILE, code)
	if (res != 0):
		code = 'latin-1'
		res = test_encoding(FILE, code)
	
	f = open(FILE, encoding=code)

	
	# First phase - build list of parts and referenced submodels

	# There are many different variations of the file format.
	# Some use FILE/NOFILE to separate different sub models which may be included by other models.
	# Some use NAME: to indicate a new model, but dont terminate it.

	output_msg.append("Phase 1 - build list of parts and referenced submodels")

	parts = list()
	files = {}
	main_model = ""
	current_file = ""
	for line in f:
		#line = line.encode("utf-8")
		#line = convert_encoding(line)
		line = line.upper()
		words = line.split()
		#output_msg.append(line)
		
		if "0 WRITE" in line:
			# Ignore
			continue
					
		if "0 GHOST" in line:
			# Ignore
			continue
			
		if "0 MLCAD HIDE" in line:
			# Ignore
			continue
		
		if line.startswith("0 ") and not line.startswith("0 FILE"):
			continue;
		
		#output_msg += "LINE(1): " + line
		if " FILE " in line or "NAME:" in line or ".DAT" in line or ".LDR" in line:
			#output_msg.append("LINE(1): " + line)
			
			# Start of a new model (including the main model)
			if (" FILE " in line or "NAME:" in line): #and (not ".DAT" in line.upper()):
				# Dont accept FILE: 1234.DAT lines as we have our own DAT file models
				name = ""
				for w in range(2, len(words)):
					name = name + words[w] + " "
				current_file = name.rstrip().lower()
			elif current_file == "":
				# No FILE/NAME line to indicate start of a model, just assume we've started an unnamed one
				current_file = "unnamed"
				
			if main_model == "":
				main_model = current_file
			
			output_msg.append("NEW FILE(1): " + current_file)
			parts = list() # list of parts/submodels within this file
			
			# The first line may be a part eg Nico's GBC
			if ".DAT" in line:
				parts.append(words[1] + '|' + words[len(words)-1].split(".")[0])
				
			if ".LDR" in line and not "NAME:" in line and not " FILE " in line and not "MLCAD HIDE" in line:
				# Using a submodel here
				name = ""
				for w in range(14, len(words)):
					name = name + words[w] + " "
				output_msg.append(" Submodel: " + name.rstrip().lower() + '(' + words[1] + ')')
				if name.rstrip().lower() == "":
					output_msg.append("ERROR - blank submodel 1 on line " + line)
					sys.exit()
				# Some submodels have a color which gets substituted instead of any 'Main Color'=16 references
				parts.append('L|' + words[1] + '|' + name.rstrip().lower())
					
			for line in f:
				#output_msg.append("LINE(2): " + line)
				#line = line.encode("utf-8")
				line = line.upper()
				words = line.split()
				
				if "0 WRITE" in line.upper():
					# Ignore
					continue
					
				if "0 GHOST" in line.upper():
					# Ignore
					continue
					
				if "0 MLCAD HIDE" in line.upper():
					# Ignore
					continue

				#output_msg += "LINE(2): " + line
							
				if "LPUB PLI BEGIN" in line.upper():
					# Designates a submodel eg 61903, or section ignored for instructions but still needed for parts eg railway tracks
					if "LPUB PLI BEGIN SUB" in line.upper():
						# Grab the model or part number
						# eg 0 !LPUB PLI BEGIN SUB 22463.dat 0
						if "LDR" in line.upper():
							if words[5].lower() == "":
								output_msg.append("ERROR - blank submodel 2 on line " + line)
								sys.exit()
							parts.append('L' + '|' + words[5].lower()) # model
						else:
							# NOTE, these do not always have a color
							if len(words)>6:
								#output_msg += words
								parts.append(words[6] + '|' + words[5].split(".")[0]) # part
							else:
								parts.append('-1|' + words[5].split(".")[0]) # part w no color
						# Following lines list sub parts, ignore them until get to END line
						for line in f:
							#output_msg.append("LINE(ignore): " + line)
							# not sure about SYNTH END, but there was no LPUB PLI END in this case
							if "LPUB PLI END" in line.upper() or "NOFILE" in line.upper() or "SYNTH END" in line.upper():
								break
					elif "LPUB PLI BEGIN IGN" in line.upper():
						# Ignored for instructions but still needed for parts eg railway tracks, so just continue as normal
						continue
						
				elif ".DAT" in line.upper():
					if words[1] == "MLCAD":
						# Hoses have this for some reason
						parts.append('0|' + words[17].split(".")[0])
					else:
						# not always 14th, eg 15th in little devil line 204, always last?
						parts.append(words[1] + '|' + words[len(words)-1].split(".")[0])
						#if "-66" in words[len(words)-1].split(".")[0]:
						#	output_msg += "WARNING: " + line
						#if "LS01" in line.upper():
						#  output_msg += "WARNING: LS01 ribbed hose found with unknown length - check instructions"
						#elif " 78.dat" in line.upper():
						#  output_msg += "WARNING: 78.dat ribbed hose found with unknown length - check instructions"
					
				elif ".LDR" in line.upper() and not "NAME:" in line.upper() and not " FILE " in line.upper() and not "MLCAD HIDE" in line.upper():
					# Grab the sub model name (may have spaces)
					# eg 1 0 60 34 300 -1 0 0 0 1 0 0 0 -1 rearaxle.ldr
					
					# Note, sometimes see the following which is a bit wierd, just ignore the recursive reference
					# 0 FILE axle3(frame).ldr
					# 0 axle3(frame).ldr
					if (len(words) < 14):
						# Not a real submodel reference, ignore it
						continue;

					name = ""
					for w in range(14, len(words)):
						name = name + words[w] + " "
					output_msg.append(" Submodel: " + name.rstrip().lower() + '(' + words[1] + ')')
					if name.rstrip().lower() == "":
						output_msg.append("ERROR - blank submodel 3 on line " + line)
						sys.exit()
					# Some submodels have a color which gets substituted instead of any 'Main Color'=16 references
					parts.append('L|' + words[1] + '|' + name.rstrip().lower())
					
				elif " NOFILE " in line.upper():
					# Finished with this file, save the parts list
					output_msg.append("Saving parts for FILE " + current_file + " (" + str(len(files)) + " parts)")
					files[current_file] = parts
					curret_file = ""
					#output_msg += "NOFILE"
					break
				
				elif " FILE " in line.upper():
					# Finished with this file, save the parts list
					output_msg.append("Saving parts for FILE " + current_file + " (" + str(len(files)) + " parts)")
					files[current_file] = parts
					name = ""
					for w in range(2, len(words)):
						name = name + words[w] + " "
					current_file = name.rstrip().lower()
					output_msg.append("NEW FILE(2): " + current_file)
					break
	
	# In case there was no NOFILE terminator
	if len(parts) > 0 and not current_file in files:
		files[current_file] = parts
		
	f.close()
	
	# Second phase - iteratively replace each submodel reference with its list of parts
	output_msg.append("Phase 2 - Replace submodel references with list of parts")

	output_msg.append("Found " + str(len(files)) + " Models")
	
	# loop through main model's parts and replace submodels with their parts
	parts = files[main_model]
	while True:
		final_parts = list()
		found_submodels = False
		output_msg.append("Processing Sub-models")
		for part in parts:
			#output_msg += part
			words = part.split('|') # color|partid OR L|modelid OR L|color|modelid
			if words[0] == 'L':
				found_submodels = True
				#output_msg += files[words[1].rstrip().lower()];
				if len(words) == 3:
					# L|color|modelid = this instance of the submodel uses a specific color to be substituted for any 'Main Color'=16 references inside the submodel definition
					#output_msg.append(" {" + words[2] + " " + words[1] + "}")
					subcolor = words[1]
					submodel = words[2].rstrip().lower()
				else:
					#output_msg.append(" {" + words[1] + "}")
					subcolor = '-1'
					submodel = words[1].rstrip().lower()
				if subcolor == '16':
					subcolor = '-1'
				output_msg.append("Expanding submodel " + submodel + " color " + subcolor + " (" + str(len(files[submodel])) + " parts)")
				if submodel in files:
					for part in files[submodel]:
						#print part + " "
						words = part.split('|')
						if words[0] == '16':
							# Main Color = substitute with subcolor. This doesn't handle nested models with 16's.
							#output_msg.append("substituting with " + subcolor);
							final_parts.append(subcolor+'|'+words[1])
						else:
							final_parts.append(part)
						#output_msg.append("part "+part)
				else:
					output_msg.append("Submodel not found! (WARNING)")
			else:
				final_parts.append(part)
				
		if found_submodels:
			parts = final_parts
		else:
			break


# End of file processing




errors = 0


lsynth_parts = ['79','80','LS00','LS01','LS02','LS03','LS04','LS05','LS06','LS07','LS08','LS09','LS10','LS11','LS20','LS20C','LS21','LS22','LS23','LS30','LS40','LS41','LS50','LS51','LS60','LS61','LS70','LS71']

# Now the final_parts list contains our full list. Parse it to do some pre-aggregation for speeding up the import process,
# as it reduces the incremental calculations required.
num_parts = 0
agg_parts = {}
for part in final_parts:
	words = part.split('|')
	
	# Drop LSynth parts
	if words[1].upper() in lsynth_parts:
		continue;
	
	if part in agg_parts:
		agg_parts[part] = agg_parts[part] + 1
	else:
		agg_parts[part] = 1
	
	num_parts = num_parts + 1

for part, qty in agg_parts.iteritems():
	words = part.split('|')
	output_parts.append({"id": words[1] , "color": words[0] , "qty": qty, "type": 1 })
	
output_msg.append("Final part count = " + str(num_parts))

if errors == 0:
	output_msg.append( "File loaded successfully.")
else:
	output_msg.append( "There were ERRORS that need to be investigated.")

print "{ \"parts\": " + json.dumps(output_parts) + ", \"msg\": " + json.dumps(output_msg) + " }"

#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(__file__.replace("__init__.py",''))
#import system_main as main
import main
import sim_module
import functions as fu
from gui import gui
import options as opt_module
import inspect
import numpy as np
import loaddata
import tempstore

#Todo: check that if works for no id and date variable
#add argument for null model (default: Y~Intercept)
#Put output functionality into the main_tabs object
#improve abort functionality, including what happens when tab is closed
#add durbin watson test:done
#output seems to be called twice
#change name of dataset (right click options?)
#make it possibel to add data by running 
#fix location issues with "+"-button. 
#create a right tab with a list of previoius estimates
#create right tab with all previously used and closed tabs available
#if one AR term is removed by reducing the AR order, the corespondig MA should be set to zero (if exists)
#have a backup for saved regressions and exe
#fix confusion about two option sets: one  in the starting environment and one in the data set
#remove copy option in main.model_parser.filter_data(data_filters,dataset,copy=False)
#Have a save symbol on all main tabs, so that the user can select a temporary folder
#save all files inside one zip-file
#check if Y is among the X variables
#add immediate command functionality to sub-pane
#add keyboard run shortcut and run selection
#make the dataset remember previoius alterations




def start():
	"""Starts the GUI"""
	tempstore.test_and_repair()
	window=gui.window()
	window.mainloop() 

def execute(model_string,dataframe, ID=None,T=None,HF=None,join_table=None,instruments=None):
	"""optimizes LL using the optimization procedure in the maximize module"""
	
	window=main.identify_global(inspect.stack()[1][0].f_globals,'window')
	exe_tab=main.identify_global(inspect.stack()[1][0].f_globals,'exe_tab')
	r=main.execute(model_string,dataframe,ID, T,HF,options,window,exe_tab,join_table,instruments)
	return r

def statistics(results,correl_vars=None,descriptives_vars=None,name=None):
	return main.stat_object.statistics(results,correl_vars,descriptives_vars,name)

def load_json(fname):

	if False:#detects previously loaded dataset in the environment
		dataframe=main.indentify_dataset(globals(),fname)
		if (not dataframe==False) and (not dataframe is None):
			return dataframe	
	try:
		dataframe=main.loaddata.load_json(fname)
	except FileNotFoundError:
		raise RuntimeError("File %s not found" %(fname))
	main.model_parser.modify_dataframe(dataframe)
	return dataframe


def load(fname,sep=None,dateformat='%Y-%m-%d',load_tmp_data=False):

	"""Loads data from file <fname>, asuming column separator <sep>.\n
	Returns a dataframe (a dictionary of numpy column matrices).\n
	If sep is not supplied, the method will attemt to find it."""
	if False:#detects previously loaded dataset in the environment
		dataframe=main.indentify_dataset(globals(),fname)
		if (not dataframe==False) and (not dataframe is None):
			return dataframe	
	try:
		dataframe=main.loaddata.load(fname,sep,dateformat,load_tmp_data)
	except FileNotFoundError:
		raise RuntimeError("File %s not found" %(fname))
	main.model_parser.modify_dataframe(dataframe)
	return dataframe

def load_SQL(conn,sql_string,dateformat='%Y-%m-%d',load_tmp_data=True):

	"""Loads data from an SQL server, using sql_string as query"""
	if False:#detects previously loaded dataset in the environment
		dataframe=main.indentify_dataset(globals(),sql_string)
		if (not dataframe==False) and (not dataframe is None):
			return dataframe
	dataframe=main.loaddata.load_SQL(conn,sql_string,dateformat,load_tmp_data)
	#except RuntimeError as e:
	#	raise RuntimeError(e)
	main.model_parser.modify_dataframe(dataframe)
	return dataframe

def filter_data(data_filters,dataset):
	d,n=main.model_parser.filter_data(data_filters,dataset,copy=False)
	return d

def edit_data(edit_script,dataset):
	exec(edit_script,dataset,dataset)
	for i in list(dataset.keys()):
		if not type(dataset[i])==np.ndarray:
			dataset.pop(i)
	window=main.identify_global(inspect.stack()[1][0].f_globals,'window')
	if hasattr(dataset,'datasets') and (not window is None):
		dataset.datasets.make_tree(dataset.name,window.right_tabs.data_tree)	
		
def add_variable(variable_name,variable_data,dataset):
	dataset[variable_name]=variable_data
	window=main.identify_global(inspect.stack()[1][0].f_globals,'window')
	if hasattr(dataset,'datasets') and (not window is None):
		dataset.datasets.make_tree(dataset.name,window.right_tabs.data_tree)	
		
		
def pool(dataframe,identifier,operation=np.mean):
	window=main.identify_global(inspect.stack()[1][0].f_globals,'window')
	p,ix=np.unique(dataframe[identifier],return_index=True)
	if len(p)==len(dataframe[identifier]):
		print(f"Data is all ready pooled on {identifier}")
		return
	N=len(p)
	
	print('pooling data ...')
	p.sort()
	p=p.reshape((N,1))
	df=dataframe
	sel=dataframe[identifier].T==p
	for k in list(dataframe.keys()):
		if type(dataframe[k])==np.ndarray:
			if k==identifier+loaddata.NON_NUMERIC_TAG:
				df[k]=dataframe[k][ix]
			elif (((loaddata.NON_NUMERIC_TAG in k) and (k!=identifier)) or 
				  (k+loaddata.NON_NUMERIC_TAG in dataframe.keys() and (k!=identifier))):
				df[k]=np.full((N,1),np.nan)
			elif k==identifier:
				df[k]=p
			else:
				df[k]=np.array([operation(dataframe[k][i]) for i in sel]).reshape((N,1))
	print('... done')
	return df
	
options=opt_module.regression_options()
preferences=opt_module.application_preferences()


#!/usr/bin/env python
# -*- coding: utf-8 -*-

#This module contains classes used in the regression



import stat_functions as stat
import numpy as np
import time
import threading
import debug
import functions as fu
import calculus_functions as cf
import model_parser
import calculus
import copy
import loglikelihood as logl
from scipy import sparse as sp
import random_effects as re


min_AC=0.000001


def posdef(a,da):
	return list(range(a,a+da)),a+da

class panel:
	def __init__(self,dataframe,datainput,settings):

			
		self.input=datainput
		self.settings=settings
		self.dataframe=dataframe
		self.initial_defs()
		self.arrayize()
		self.masking()
		self.lag_variables()
		self.final_defs()


	def masking(self):
		
		#"initial observations" mask: 
		self.a=np.array([self.date_counter<self.T_arr[i] for i in range(self.N)])# sets observations that shall be zero to zero by multiplying it with the arrayized variable
	
		#"after lost observations" masks: 
		self.T_i=np.sum(self.included,1).reshape((self.N,1,1))#number of observations for each i
		self.T_i=self.T_i+(self.T_i<=0)#ensures minimum of 1 observation in order to avoid division error. If there are no observations, averages will be zero in any case	
		self.N_t=np.sum(self.included,0).reshape((1,self.max_T,1))#number of observations for each i
		self.N_t=self.N_t+(self.N_t<=0)#ensures minimum of 1 observation in order to avoid division error. If there are no observations, averages will be zero in any case	
		self.group_var_wght=1-1/np.maximum(self.T_i-1,1)
		
	def initial_defs(self):

		if np.all(np.var(self.input.Y,0)==0):
			raise RuntimeError("No variation in Y")
		self.tobit_set_threshold()
		p,q,d,m,k=self.settings.pqdmk
		self.lost_obs=np.max((p,q))+max((m,k))+d#+3
		self.nW,self.n_beta=self.input.W.shape[1],self.input.X.shape[1]
		self.define_h_func()	
		
		if self.input.IDs_name is None:
			self.settings.group_fixed_random_eff=0
		if self.settings.group_fixed_random_eff==0:
			self.input.timevar=None			
		self.m_zero = False
		if  m==0 and k>0:
			self.m_zero = True
			p,q,d,m,k=self.settings.pqdmk
			self.settings.pqdmk=p,q,d,1,k
	
	
		
	def final_defs(self):
		self.W_a=self.W*self.a
		self.tot_lost_obs=self.lost_obs*self.N
		self.NT=np.sum(self.included)
		self.NT_before_loss=self.NT+self.tot_lost_obs				
		self.number_of_RE_coef=self.N
		self.number_of_FE_coef_in_variance=self.N
		self.args=arguments(self, )
		self.df=self.NT-self.args.n_args-self.number_of_RE_coef-self.number_of_FE_coef_in_variance

	def lag_variables(self):
		T=self.max_T
		d=self.settings.pqdmk[2]
		self.I=np.diag(np.ones(T))
		self.zero=np.zeros((T,T))		

		#differencing:
		if d==0:
			return
		L0=np.diag(np.ones(T-1),-1)
		Ld=(self.I-L0)
		for i in range(1,d):
			Ld=cf.dot(self.I-L0,self.Ld)		
		self.Y=cf.dot(Ld,self.Y)*self.a	
		self.X=cf.dot(Ld,self.X)*self.a
		if self.input.has_intercept:
			self.X[:,:,0]=1
		self.Y[:,:d]=0
		self.X[:,:d]=0	

	def params_ok(self,args):
		a=self.q_sel,self.p_sel,self.M_sel,self.K_sel
		for i in a:
			if len(i)>0:
				if np.any(np.abs(args[i])>0.999):
					return False
		return True


	def arrayize(self):
		"""Splits X and Y into an arry of equally sized matrixes rows equal to the largest for each IDs"""
		X, Y, W, IDs=self.input.X, self.input.Y, self.input.W, self.input.IDs
		timevar=self.input.timevar
		NT,k=X.shape
		if IDs is None:
			self.X=X.reshape((1,NT,k))
			self.Y=Y.reshape((1,NT,1))
			for i in [0,1]:
				self.tobit_I[i].resize((1,NT,1))
			NTW,k=W.shape
			self.W=W.reshape((1,NT,k))
			self.time_map=None
			self.N=1
			self.max_T=NT
			self.T_arr=np.array([[NT]])
		else:
			sel=np.unique(IDs)
			N=len(sel)
			sel=(IDs.T==sel.reshape((N,1)))
			T=np.sum(sel,1)
			self.max_T=np.max(T)
			idincl=T>self.lost_obs+5
			self.X=arrayize(X, N,self.max_T,T, idincl,sel)
			self.Y=arrayize(Y, N,self.max_T,T, idincl,sel)
			for i in [0,1]:
				self.tobit_I[i]=arrayize(self.tobit_I[i], N,self.max_T,T, idincl,sel,dtype=bool)
			self.W=arrayize(W, N,self.max_T,T, idincl,sel)
			self.N=np.sum(idincl)
			self.T_arr=T[idincl].reshape((self.N,1))
			self.date_counter=np.arange(self.max_T).reshape((self.max_T,1))
			self.included=np.array([(self.date_counter>=self.lost_obs)*(self.date_counter<self.T_arr[i]) for i in range(self.N)])
			self.get_time_map(timevar, self.N,T, idincl,sel)
			
	
			idremoved=np.arange(N)[idincl==False]
			if len(idremoved):
				s=fu.formatarray(idremoved,90,', ')
				print("Warning: The following ID's were removed because of insufficient observations:\n %s" %(s))
		self.allzeros=np.zeros((self.N,self.max_T,1))

	
	def get_time_map(self,timevar, N,T, idincl,sel):
		if timevar is None:
			return None
		unq,ix=np.unique(timevar,return_inverse=True)
		t=arrayize(np.array((ix,)).T+1, N,self.max_T,T, idincl,sel,int)
		N,T,k=t.shape
		t=t.reshape(N*T)
		t=np.array((t,np.arange(N*T))).T
		t=t[np.nonzero(self.included.reshape(N*T))]
		a=np.argsort(t[:,0])
		t=t[a]
		grp=np.array(t[:,1]/self.max_T,dtype=int)
		day=t[:,1]-grp*self.max_T
		t=np.array((t[:,0]-1,grp,day)).T
	
		tid=t[:,0]
		t_map=[[] for i in range(np.max(tid)+1)]
		for i in range(len(tid)):
			t_map[tid[i]].append(t[i,1:])
		t_map_tuple=[]
		tcnt=[]
		self.date_count_mtrx=np.zeros((N,T,1))
		for i in range(len(t_map)):
			a=np.array(t_map[i]).T
			if len(a):
				m=(tuple(a[0]),tuple(a[1]))
				n_t=len(a[0])
				t_map_tuple.append(m)	
				tcnt.append(n_t)
				self.date_count_mtrx[m]=n_t
				
		
		#A full random effects calculation is infeasible because of complexity and computing costs. 
		#A quazi random effects weighting is used. It  is more conservative than the full
		#RE weight theta=1-sd_pooled/(sd_pooled+sd_within/T)**0.5
		#If the weights are too generous, the RE adjustment may add in stead of reducing noise. 
		n=len(tcnt)
		self.n_dates=n
		self.date_count=np.array(tcnt).reshape(n,1,1)
		self.date_map=t_map_tuple
		
		
	
	
	def define_h_func(self):
		h_def="""
def h(e,z):
	e2			=	e**2+1e-5
	h_val		=	np.log(e2)	
	h_e_val		=	2*e/e2
	h_2e_val	=	2/e2-4*e**2/e2**2

	return h_val,h_e_val,h_2e_val,None,None,None
		"""	
		h_definition=self.settings.h_function
		if h_definition is None:
			h_definition=h_def
		d=dict()
		try:
			exec(h_definition,globals(),d)
			ret=d['h'](1,1)
			if len(ret)!=6:
				raise RuntimeError("""Your custom h-function must return exactly six arguments
				(h, dh/dx and ddh/dxdx for both e and z. the z return values can be set to None)""")
			self.h_def=h_definition
		except Exception as e:
			print('Something is wrong with your custom function, default is used:'+ str(e))
			exec(h_def,globals(),d)
			self.h_def=h_def
		
		self.z_active=True
		for i in ret[3:]:
			self.z_active=self.z_active and not (i is None)	
		if not self.settings.user_constraints is None:
			if not self.z_active and 'z' in self.settings.user_constraints:
				self.settings.user_constraints.pop('z')
			

		
		
	def mean(self,X,axis=None):
		dims=list(X.shape)
		dims[2:]=[1]*(len(dims)-2)
		#X=X*self.included.reshape(dims)
		if axis==None:
			return np.sum(X)/self.NT
		if axis==1:
			dims.pop(1)
			return np.sum(X,1)/self.T_i.reshape(dims)
		if axis==0:
			dims.pop(0)
			return np.sum(X,0)/self.N_t.reshape(dims)
		if axis==(0,1):
			return np.sum(np.sum(X,0),0)/self.NT
			
	def var(self,X,axis=None,k=1,mean=None):
		dims=list(X.shape)
		dims_m=np.array(X.shape)
		dims[2:]=[1]*(len(dims)-2)	
		#X=X*self.included.reshape(dims)
		if mean is None:
			m=self.mean(X, axis)
		else:
			m=mean

		if axis==None:
			return np.sum((X-m)**2)/(self.NT-k)
		count=[]
		if axis==1:
			dims_m[1]=1
			dims.pop(1)
			m=m.reshape(dims_m)
			Xm=(X-m)#*self.included.reshape(dims)			
			return np.sum((Xm)**2,1)/np.maximum(self.T_i-k,1).reshape(dims)
		if axis==0:
			dims_m[0]=1		
			dims.pop(0)
			m=m.reshape(dims_m)
			Xm=(X-m)#*self.included.reshape(dims)			
			return np.sum((Xm)**2,0)/np.maximum(self.N_t-k,1).reshape(dims)
		if axis==(0,1):
			dims_m[0:2]=1
			m=m.reshape(dims_m)
			Xm=(X-m)#*self.included.reshape(dims)			
			return np.sum((Xm)**2,axis)/(self.NT-k)
		
	def tobit_set_threshold(self):
		"""Sets the tobit threshold"""
		tobit_limits=self.settings.tobit_limits
		Y=self.input.Y
		if tobit_limits is None:
			return
		if len(tobit_limits)!=2:
			print("Warning: The tobit_limits argument must have lenght 2, and be on the form [floor, ceiling]. None is used to indicate no active limit")
		if (not (tobit_limits[0] is None)) and (not( tobit_limits[1] is None)):
			if tobit_limits[0]>tobit_limits[1]:
				raise RuntimeError("floor>ceiling. The tobit_limits argument must have lenght 2, and be on the form [floor, ceiling]. None is used to indicate no active limit")
		g=[1,-1]
		self.tobit_active=[False, False]
		self.tobit_I=[None,None]
		for i in [0,1]:
			self.tobit_active[i]=not (tobit_limits[i] is None)
			if self.tobit_active[i]:
				if np.sum(g[i]*Y<g[i]*tobit_limits[i]):
					print("Warning: there are observations of Y outside the non-cencored interval. These ")
				I=g[i]*Y<=g[i]*tobit_limits[i]
				Y[I]=tobit_limits[i]
				if np.var(Y)==0:
					raise RuntimeError("Your tobit limits are too restrictive. All observationss were cencored.")
				self.tobit_I[i]=I		
	
def arrayize(X,N,max_T,T,idincl,sel,dtype=None):
	if X is None:
		return None
	NT,k=X.shape
	if dtype is None:
		Xarr=np.zeros((N,max_T,k))
	else:
		Xarr=np.zeros((N,max_T,k),dtype=dtype)
	T_used=[]
	k=0
	for i in range(len(sel)):
		if idincl[i]:
			Xarr[k,:T[i]]=X[sel[i]]
			k+=1
	Xarr=Xarr[:k]
	return Xarr





class arguments:
	"""Sets initial arguments and stores static properties of the arguments"""
	def __init__(self,panel):
		args=panel.input.args
		p, q, d, m, k=panel.settings.pqdmk
		self.categories=['beta','rho','lambda','gamma','psi','omega']
		if panel.z_active:
			self.categories+=['z']
		self.mu_removed=True
		if not self.mu_removed:
			self.categories+=['mu']
		
		self.args_old=args
		self.panel=panel
		self.set_init_args(p, d, q, m, k,panel)
		self.make_namevector(panel,p, q, m, k)
		self.position_defs()
		self.args_v=self.conv_to_vector(self.args_init)
		self.n_args=len(self.args_v)
		

	def initargs(self,p,d,q,m,k,panel):
		if self.args_old is None:
			armacoefs=0
		else:
			armacoefs=0
		args=dict()
		args['beta']=np.zeros((panel.X.shape[2],1))
		args['omega']=np.zeros((panel.W.shape[2],1))
		args['rho']=np.ones(p)*armacoefs
		args['lambda']=np.ones(q)*armacoefs
		args['psi']=np.ones(m)*armacoefs
		args['gamma']=np.ones(k)*armacoefs
		args['omega'][0][0]=0
		args['mu']=np.array([])
		args['z']=np.array([])			
		if m>0:
			args['psi'][0]=0
			
		if m>0 and panel.z_active:
			args['z']=np.array([1e-09])	

		if panel.N>1 and not self.mu_removed:
			args['mu']=np.array([0.0001])			
			

		return args

	def set_init_args(self,p,d,q,m,k,panel):
		
		args=self.initargs(p, d, q, m, k, panel)

		#de2=np.roll(e**2,1)-e**2
		#c=stat.correl(np.concatenate((np.roll(de2,1),de2),2),panel)[0,1]

		beta,e=stat.OLS(panel,panel.X,panel.Y,return_e=True)
		args['beta']=beta
		if panel.settings.group_fixed_random_eff==0:
			args['omega'][0]=np.log(panel.var(e))

	
		self.args_start=fu.copy_array_dict(args)
		if not self.args_old is None: 
			args['beta']=insert_arg(args['beta'],self.args_old['beta'])
			if panel.settings.group_fixed_random_eff==0:
				args['omega']=insert_arg(args['omega'],self.args_old['omega'])
			args['rho']=insert_arg(args['rho'],self.args_old['rho'])
			args['lambda']=insert_arg(args['lambda'],self.args_old['lambda'])
			args['psi']=insert_arg(args['psi'],self.args_old['psi'])
			args['gamma']=insert_arg(args['gamma'],self.args_old['gamma'])
			if panel.z_active:
				args['z']=insert_arg(args['z'],self.args_old['z'])
			if not self.mu_removed:
				args['mu']=insert_arg(args['mu'],self.args_old['mu'])
			
		self.args_init=args
		self.set_restricted_args(p, d, q, m, k,panel,e,beta)
		

	def set_restricted_args(self,p, d, q, m, k, panel,e,beta):
		self.args_restricted=self.initargs(p, d, q, m, k, panel)
		self.args_OLS=self.initargs(p, d, q, m, k, panel)		
		self.args_restricted['beta'][0][0]=np.mean(panel.Y)
		self.args_restricted['omega'][0][0]=np.log(np.var(panel.Y))
		self.args_OLS['beta']=beta
		self.args_OLS['omega'][0][0]=np.log((np.var(e*panel.included)*len(e[0])/np.sum(panel.included)))
		
	def position_defs(self):
		"""Defines positions in vector argument"""

		self.positions=dict()
		self.positions_map=dict()#a dictionary of indicies containing the string name and sub-position of index within the category
		k=0
		for i in self.categories:
			n=len(self.args_init[i])
			rng=range(k,k+n)
			self.positions[i]=rng
			for j in rng:
				self.positions_map[j]=[0,i,j-k]#equation,category,position
			k+=n
	
	def conv_to_dict(self,args):
		"""Converts a vector argument args to a dictionary argument. If args is a dict, it is returned unchanged"""
		if type(args)==dict:
			return args
		else:
			d=dict()
			k=0
			for i in self.categories:
				n=len(self.positions[i])
				rng=range(k,k+n)
				d[i]=args[rng]
				if i=='beta' or i=='omega':
					d[i]=d[i].reshape((n,1))
				k+=n
		return d


	def conv_to_vector(self,args):
		"""Converts a dict argument args to vector argument. if args is a vector, it is returned unchanged.\n
		If args=None, the vector of self.args_init is returned"""
		if type(args)==list or type(args)==np.ndarray:
			return args
		v=np.array([])
		for i in self.categories:
			s=args[i]
			if type(s)==np.ndarray:
				s=s.flatten()
			v=np.concatenate((v,s))
		return v


	def make_namevector(self,panel,p, q, m, k):
		"""Creates a vector of the names of all regression varaibles, 
		including variables, ARIMA and GARCH terms. This defines the positions
		of the variables througout the estimation."""
		d=dict()
		names=panel.input.x_names[:]#copy variable names
		d['beta']=list(names)
		add_names(p,'AR term %s (p)','rho',d,names)
		add_names(q,'MA term %s (q)','lambda',d,names)
		add_names(m,'MACH term %s (m)','gamma',d,names)
		add_names(k,'ARCH term %s (k)','psi',d,names)
		
		d['omega']=panel.input.W_names
		names.extend(panel.input.W_names)
		if m>0:
			if panel.N>1 and not self.mu_removed:
				d['mu']=['mu (var.ID eff.)']
				names.extend(d['mu'])
			if panel.z_active:
				d['z']=['z in h(e,z)']
				names.extend(d['z'])
			
		self.names_v=names
		self.names_d=d


			

			
def add_names(T,namsestr,category,d,names):
	a=[]
	for i in range(T):
		a.append(namsestr %(i,))
	names.extend(a)
	d[category]=a
	

def insert_arg(arg,add):
	n=min((len(arg),len(add)))
	arg[:n]=add[:n]
	return arg
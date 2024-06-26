#!/usr/bin/env python
# -*- coding: utf-8 -*-

from ..output import stat_functions as stat
from ..output import stat_dist
from .. import functions as fu
from . import constraints
from .. import likelihood as logl
import sys

from . import direction

import numpy as np


EPS=3.0e-16 
TOLX=(4*EPS) 
STPMX=100.0 



class Computation:
	def __init__(self,args, panel, gtol, tolx, betaconstr, iterative_constr=[]):
		self.gradient=logl.calculus.gradient(panel)
		self.gtol = panel.options.tolerance.value
		self.tolx = tolx
		self.hessian=logl.hessian(panel,self.gradient)
		self.panel=panel
		self.constr=None
		self.iterative_constr = iterative_constr
		self.CI=0
		self.weak_mc_dict={}
		self.mc_problems=[]
		self.H_correl_problem=False
		self.singularity_problems=False
		self.num_hess_count = 0
		self.H, self.g, self.G = None, None, None
		self.mcollcheck = False
		self.rec =[]
		self.quit = False
		self.avg_incr = 0
		self.errs = []
		self.CI_anal = 2
		p, q, d, k, m = panel.pqdkm
		self.init_arma_its = 0
		self.betaconstr = betaconstr
		self.set_constr(args, iterative_constr,  panel.options.ARMA_constraint.value)
		





	def set(self, its,increment,lmbda,rev, H, ll, x, armaconstr):
		self.its=its
		self.lmbda=lmbda
		self.has_reversed_directions=rev
		self.increment=increment
	
		self.constr_old=self.constr
		self.constr = None
		self.constr = constraints.Constraints(self.panel,x,its,armaconstr, self.betaconstr)

		if self.constr is None:
			self.H_correl_problem,self.mc_problems,self.weak_mc_dict=False, [],{}
			self.singularity_problems=(len(self.mc_problems)>0) or self.H_correl_problem
			return

		if self.panel.options.constraints_engine.value:
			self.constr.add_static_constraints(self.panel, its, ll, self.iterative_constr)	

			self.constr.add_dynamic_constraints(self, H, ll)	

		self.CI=self.constr.CI
		self.H_correl_problem=self.constr.H_correl_problem	
		self.mc_problems=self.constr.mc_problems
		self.weak_mc_dict=self.constr.weak_mc_dict
		


	def exec(self, dx_realized,hessin, H, incr, its, ls, armaconstr):
		f, x, g_old, rev, alam,ll = ls.f, ls.x, ls.g, ls.rev, ls.alam, ls.ll
		#These setting may not hold for all circumstances, and should be tested properly:

		
		TOTP_TOL = 1e-15


		g, G = self.calc_gradient(ll)
		if np.max(np.abs(g))>1e+50:
			return x, f, hessin, H, G, g, 0, None, 0
		dx, dx_norm, H_ = direction.get(g, x, H, self.constr, f, hessin, simple=False)

		a = np.ones(len(g))
		if not self.constr is None:
			a[list(self.constr.fixed.keys())] =0		
			a[ls.applied_constraints] = 0    

		pgain, totpgain = potential_gain(dx*a, g, H)
		self.totpgain = totpgain
		max_pgain = abs(max(pgain))


		g_norm =np.max(np.abs(g*a*x)/(abs(f)+1e-12) )
		gtol = self.gtol
			
		if sum(a)==1:
			gtol = 1e-10
		self.rec.append(str(i) for i in [totpgain, max_pgain, incr, g_norm])
		CI=0
		if not self.CI is None:
			CI = self.CI



		se = [None]*len(H)	
		err = np.max(np.abs(dx_realized)) < 10000*TOLX
		self.errs.append(err)

		hessin, H, conv, se = self.handle_convergence(ll, H, hessin, totpgain, its, TOTP_TOL, ls, g_norm, se, G, incr)
		if conv:
			return x, f, hessin, H, G, g, conv, se, g_norm

		if not self.panel.options.supress_output.value:
			print(f"its:{its}, f:{f}, gnorm: {abs(g_norm)}, totpgain: {abs(totpgain)}")
			sys.stdout.flush()

		self.avg_incr = incr + self.avg_incr*0.7
		self.ev_constr = False#self.CI>1000

		
		h_det = fu.try_warn(np.linalg.det, (H,))
		hessin_det = fu.try_warn(np.linalg.det, (hessin,))


		if self.panel.options.use_analytical.value==2:
			analytic_calc = not ((self.CI>100) 
											 or err 
											 or (not 0 < abs(h_det) < 1e+30)
											 or (not 0 < abs(hessin_det) < 1e+30))
		elif self.panel.options.use_analytical.value==1:
			analytic_calc = ((self.CI>100) 
											 or err 
											 or (not 0 < abs(h_det) < 1e+30)
											 or (not 0 < abs(hessin_det) < 1e+30))
		else:
			analytic_calc = False

		if analytic_calc:
			H = self.calc_hessian(ll)
			a = 1.0
			try:
				hessin = np.linalg.inv(H)*a + (1-a)*hessin
			except:
				pass
			self.num_hess_count = 0

		else:
			self.num_hess_count +=1
			try:
				hessin=self.hessin_num(hessin, g-g_old, dx_realized)
				Hn = np.linalg.inv(hessin)
				H = Hn
			except:
				H = self.calc_hessian(ll)

		self.set(its, ls.f - f, ls.alam, ls.rev,  H, ls.ll, ls.x, armaconstr)

		self.H, self.g, self.G = H, g, G

		return x, f, hessin, H, G, g, 0, se, g_norm
	
	def set_constr(self, args, constr, armaconstr):
		self.constr = constraints.Constraints(self.panel, args, 0, armaconstr, self.betaconstr)
		self.constr.add_static_constraints(self.panel, 0, constr=constr)	    

	def handle_convergence(self, ll, H, hessin, totpgain, its, TOTP_TOL, ls, g_norm, se, G, incr):
		if its<len(self.constr.constr_matrix)+2:
			return hessin, H, 0, se
		
		conv = 0

		if abs(g_norm) < self.gtol:
			conv = 1
		elif abs(totpgain)<TOTP_TOL:
			conv = 2
		elif its>=self.panel.options.max_iterations.value:
			conv = 3
		elif ((sum(self.errs[-3:])==10) and ls.alam<1e-5) or ((sum(self.errs[-3:])==3) and incr<1e-15): #stalled: 3 consectutive errors and small ls.alam, or no function increase
			conv = 4
		elif self.constr.CI>10000 and len(self.constr.mc_list) and False:
			conv = 5
		if not conv:
			return hessin, H, 0, se
		return hessin, H, conv, se
		Ha = self.calc_hessian(ll)    
		keep = [True]*len(H)
		if not self.constr is None:      
			self.constr.add_dynamic_constraints(self, Ha, ll,ll.args.args_v)
			keep = [not i in self.constr.fixed.keys() for i in range(len(H))]
		Ha_keep = Ha[keep][:,keep]
		self.CI_anal = condition_index(Ha_keep)
		try:
			det = np.linalg.det(Ha_keep)
			hessin[keep][:,keep] = np.linalg.inv(Ha_keep)
			se = stat.robust_se(self.panel, 100, hessin, G)[0]				
		except Exception as e:
			print(e)



		return hessin, Ha, conv, se  

 
		
	def calc_gradient(self,ll):
		dLL_lnv, DLL_e=logl.func_gradent(ll,self.panel)
		self.LL_gradient_tobit(ll, DLL_e, dLL_lnv)
		g, G = self.gradient.get(ll,DLL_e,dLL_lnv,return_G=True)
		return g, G


	def calc_hessian(self, ll):
		d2LL_de2, d2LL_dln_de, d2LL_dln2 = logl.func_hessian(ll,self.panel)
		self.LL_hessian_tobit(ll, d2LL_de2, d2LL_dln_de, d2LL_dln2)
		H = self.hessian.get(ll,d2LL_de2,d2LL_dln_de,d2LL_dln2)	
		return H

	def LL_gradient_tobit(self,ll,DLL_e,dLL_lnv):
		g=[1,-1]
		self.f=[None,None]
		self.f_F=[None,None]
		for i in [0,1]:
			if self.panel.tobit_active[i]:
				I=self.panel.tobit_I[i]
				self.f[i]=stat_dist.norm(g[i]*ll.e_norm[I], cdf = False)
				self.f_F[i]=(ll.F[i]!=0)*self.f[i]/(ll.F[i]+(ll.F[i]==0))
				self.v_inv05=ll.v_inv**0.5
				DLL_e[I]=g[i]*self.f_F[i]*self.v_inv05[I]
				dLL_lnv[I]=-0.5*DLL_e[I]*ll.e_RE[I]
				a=0


	def LL_hessian_tobit(self,ll,d2LL_de2,d2LL_dln_de,d2LL_dln2):
		g=[1,-1]
		if sum(self.panel.tobit_active)==0:
			return
		self.f=[None,None]
		e1s1=ll.e_norm
		e2s2=ll.e_REsq*ll.v_inv
		e3s3=e2s2*e1s1
		e1s2=e1s1*self.v_inv05
		e1s3=e1s1*ll.v_inv
		e2s3=e2s2*self.v_inv05
		f_F=self.f_F
		for i in [0,1]:
			if self.panel.tobit_active[i]:
				I=self.panel.tobit_I[i]
				f_F2=self.f_F[i]**2
				d2LL_de2[I]=      -(g[i]*f_F[i]*e1s3[I] + f_F2*ll.v_inv[I])
				d2LL_dln_de[I] =   0.5*(f_F2*e1s2[I]  +  g[i]*f_F[i]*(e2s3[I]-self.v_inv05[I]))
				d2LL_dln2[I] =     0.25*(f_F2*e2s2[I]  +  g[i]*f_F[i]*(e1s1[I]-e3s3[I]))


	def hessin_num(self, hessin, dg, xi):				#Compute difference of gradients,
		n=len(dg)
		#and difference times current matrix:
		hdg=(np.dot(hessin,dg.reshape(n,1))).flatten()
		fac=fae=sumdg=sumxi=0.0 							#Calculate dot products for the denominators. 
		fac = np.sum(dg*xi) 
		fae = np.sum(dg*hdg)
		sumdg = np.sum(dg*dg) 
		sumxi = np.sum(xi*xi) 
		if (fac < (EPS*sumdg*sumxi)**0.5):  					#Skip update if fac not sufficiently positive.
			fac=1.0/fac 
			fad=1.0/fae 
															#The vector that makes BFGS different from DFP:
			dg=fac*xi-fad*hdg   
			#The BFGS updating formula:
			hessin+=fac*xi.reshape(n,1)*xi.reshape(1,n)
			hessin-=fad*hdg.reshape(n,1)*hdg.reshape(1,n)
			hessin+=fae*dg.reshape(n,1)*dg.reshape(1,n)		

		return hessin



def det_managed(H):
	try:
		return np.linalg.det(H)
	except:
		return 1e+100

def inv_hess(hessian):
	try:
		h=-np.linalg.inv(hessian)
	except:
		return None	
	return h

def condition_index(H):
	n = len(H)
	d=np.maximum(np.abs(np.diag(H)).reshape((n,1)),1e-30)**0.5
	C = -H/(d*d.T)
	ev = np.abs(np.linalg.eigvals(C))**0.5
	if min(ev) == 0:
		return 1e-150
	return max(ev)/min(ev)	


def hess_inv(h, hessin):
	try:
		h_inv = np.linalg.inv(h)
	except Exception as e:
		print(e)
		return hessin
	return h_inv



def potential_gain(dx, g, H):
	"""Returns the potential gain of including each variables, given that all other variables are included and that the 
	quadratic model is correct. An alternative convercence criteria"""
	n=len(dx)
	rng=np.arange(len(dx))
	dxLL=dx*0
	dxLL_full=(sum(g*dx)+0.5*np.dot(dx.reshape((1,n)),
																	np.dot(H,dx.reshape((n,1)))
																	))[0,0]
	for i in range(len(dx)):
		dxi=dx*(rng!=i)
		dxLL[i]=dxLL_full-(sum(g*dxi)+0.5*np.dot(dxi.reshape((1,n)),np.dot(H,dxi.reshape((n,1)))))[0,0]

	return dxLL, dxLL_full




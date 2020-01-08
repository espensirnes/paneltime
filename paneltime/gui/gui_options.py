#!/usr/bin/env python
# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk
from gui import gui_charts
import time
from gui import gui_scrolltext
import options as default_options

NON_NUMERIC_TAG='|~|'
font='Arial 9 '
tags=dict()
tags['dependent']={'fg':'#025714','bg':'#e6eaf0','font':font+'bold','short':'Y'}
tags['independent']={'fg':'#053480','bg':'#e6eaf0','font':font+'bold','short':'X'}
tags['time variable']={'fg':'#690580','bg':'#e6eaf0','font':font+'bold','short':'T'}
tags['id variable']={'fg':'#910101','bg':'#e6eaf0','font':font+'bold','short':'ID'}
tags['het.sc._factors']={'fg':'#029ea3','bg':'#e6eaf0','font':font+'bold','short':'HF'}
unselected={'fg':'black','bg':'white','font':font,'short':''}
#for correct sorting:
tags_list=['dependent','independent','time variable','id variable','het.sc._factors']

class options(ttk.Treeview):
		
	def __init__(self,tabs,window):
		s = ttk.Style()
		s.configure('new.TFrame', background='white',font=font)			
		self.tabs=tabs
		self.win=window
		self.options=window.globals['options']
		self.default_options=default_options.options()
		self.main_frame=tk.Frame(tabs)
		self.canvas=tk.Canvas(self.main_frame)
		self.opt_frame=tk.Frame(self.main_frame)

		
		ttk.Treeview.__init__(self,self.canvas,style='new.TFrame')
		
		self.data_frames=dict()
		self.data_frames_source=dict()
		self.level__dicts=[dict(),dict(),dict()]
		
		yscrollbar = ttk.Scrollbar(self.canvas, orient="vertical", command=self.yview)
		self.configure(yscrollcommand=yscrollbar.set)
		
		xscrollbar = ttk.Scrollbar(self.canvas, orient="horizontal", command=self.xview)
		self.configure(xscrollcommand=xscrollbar.set)
		
		self.gridding(xscrollbar,yscrollbar)
		self.tree_construction()
		self.binding()
			
		self.tabs.add(self.main_frame, text='options')      # Add the tab
		self.tabs.grid(row=0,column=0,sticky=tk.NSEW)  # Pack to make visible	
		
	def binding(self):
		self.bind('<Double-Button-1>',self.tree_double_click)	
		self.bind('<<TreeviewSelect>>',self.tree_click)	
		self.bind('<Key>',self.key_down)	
		self.bind('<KeyRelease>',self.key_up)		
		
	def tree_construction(self):
		self["columns"]=("one","two")
		self.column("#0", stretch=tk.YES)
		self.column("one", width=15,stretch=tk.YES)
		self.column("two", width=75,stretch=tk.YES)
		self.heading("#0",text="Option",anchor=tk.W)
		self.heading("one", text="",anchor=tk.W)
		self.heading("two", text="value",anchor=tk.W)	
		self.alt_time=time.perf_counter()
		for k in tags_list:
			tag_configure(self,k,tags[k])	
		self.tree=dict()		
		
	def gridding(self,xscrollbar,yscrollbar):
		self.rowconfigure(0,weight=1)
		self.columnconfigure(0,weight=1)
		self.tabs.rowconfigure(0,weight=1)
		self.tabs.columnconfigure(0,weight=1)
		
		self.main_frame.rowconfigure(0,weight=5)
		self.main_frame.rowconfigure(1,weight=7)
		self.main_frame.columnconfigure(0,weight=1)
		self.canvas.rowconfigure(0,weight=1)
		self.canvas.columnconfigure(0,weight=1)		
		self.opt_frame.rowconfigure(0,weight=1)
		self.opt_frame.columnconfigure(0,weight=1)				
		
		self.main_frame.grid(row=0,column=0,sticky=tk.NSEW)
		self.canvas.grid(row=0,column=0,sticky=tk.NSEW)	
		self.opt_frame.grid(row=1,column=0,sticky=tk.NSEW)	
		
		xscrollbar.grid(row=1,column=0,sticky='ew')
		yscrollbar.grid(row=0,column=1,sticky='ns')	
		self.grid(row=0,column=0,sticky=tk.NSEW)			
		
	def key_down(self,event):
		if event.keysym=='Alt_L' or  event.keysym=='Alt_R':
			self.configure(cursor='target')
			self.alt_time=time.perf_counter()
			
			
	def key_up(self,event):
		if event.keysym=='Alt_L' or  event.keysym=='Alt_R':
			self.configure(cursor='arrow')

		
	def tree_double_click(self,event):
		item = self.selection()[0]
		item=self.item(item)['text']
		self.win.main_tabs.insert_current_editor(item)
		
	def tree_click(self,event):
		item = self.selection()
		if len(item)==0:
			return
		item=item[0]
		levels=item.split(';')
		if levels[1]=='':#is top level
			return
		if len(levels)==3:
			parent_itm=';'.join(levels[:-1])
			fname,j,k=levels
			short,vtype=self.item(parent_itm)['values']
			s=tags[k]['short']
			if s=='Y' or s=='T' or s=='ID':
				for i in self.tree[fname]:
					short_i,vtype_i=self.item(i)['values']
					if s==short_i:
						tag_configure(self,i,unselected,('',vtype_i))
			tag_configure(self,parent_itm,tags[k])
			self.item(parent_itm,values=(tags[k]['short'],vtype))
			self.item(parent_itm,open=False)
		elif len(levels)==2:
			i,j=levels
			item_obj=self.item(item)
			short,vtype=item_obj['values']
			t=self.tag_configure(item)	
			if item_obj['open']:
				if t['font']!=unselected['font']:
					tag_configure(self,item,unselected,('',vtype))
				else:
					self.close_all()
			else:
				if time.perf_counter()-self.alt_time<0.1:#alt pressed
					if short=='':
						tag_configure(self,item,tags['independent'],('X',vtype))
					else:
						tag_configure(self,item,unselected,('',vtype))
				else:
					self.close_all()
					self.item(item,open=True)
					
			
	def close_all(self):
		for i in self.tree:
			for j in self.tree[i]:
				self.item(j,open=False)
		
	def get_selected_df(self):
		item = self.selection()
		if len(item)==0:
			raise RuntimeError('No data frame dictionary is selected in the right pane, or data has not been imported')
		item=self.item(item[0])['text']
		return self.data_frames[f"{fname};"]		
		
	def add_options_to_tree(self):
		opt=self.options.__dict__
		for i in opt:
			
		try:
			self.insert('', 1,f"{fname};", text=fname)
		except tk.TclError:
			self.delete(f"{fname};")
			self.insert('', 1,f"{fname};", text=fname)
		self.add_node(df,fname)
		self.tabs.select(self.main_frame)
		self.item(f"{fname};",open=True)
				
	def add_node(self,df,fname):
		a=[]
		self.tree[fname]=a
		for j in df:
			nptype=np_type(j,df)
			if nptype!='na':
				self.insert(f"{fname};",2, f"{fname};{j}", text=j,values=('',nptype),tags=(f"{fname};{j}",))	
				a.append(f"{fname};{j}")
				for k in tags_list:
					self.insert(f"{fname};{j}",3, f"{fname};{j};{k}",values=('',tags[k]['short']), text=k,tags=(k,))

		
		


def np_type(name,df):
	x=df[name]
	if NON_NUMERIC_TAG in name or name=='ones':
		return 'na'
	non_num=name+NON_NUMERIC_TAG
	if non_num in df:
		x=df[non_num]
	nptype='na'
	t=str(type(x)).replace(' ','')[7:][:-2]
	if t.split('.')[0]=='numpy':
		nptype=str(x.dtype)		
	return nptype


def tag_configure(tree,name,d,value=None):
	
	tree.tag_configure(name, foreground=d['fg'])
	tree.tag_configure(name, background=d['bg'])
	tree.tag_configure(name, font=d['font'])	
	if not value is None:
		tree.item(name,value=value)
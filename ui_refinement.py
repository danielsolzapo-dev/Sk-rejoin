"""Compact desktop composition. Presentation only: no service or session mutations."""
import tkinter as tk
from tkinter import ttk, font as tkfont
import re
import theme
from ui_text import tr


def semantic_state(row):
    text = (str(row.get('status', '')) + ' ' + str(row.get('connection', ''))).casefold()
    if row.get('errorCode') or any(word in text for word in ('erro', 'recusad', 'falhou')):
        return 'error'
    if any(word in text for word in ('block acc', 'troca de servidor', 'trocando', 'aviso')):
        return 'block'
    if any(word in text for word in ('aguardando', 'carregando', 'abrindo', 'ticket', 'protocolo')):
        return 'loading'
    if row.get('age') is not None and row['age'] < 20:
        return 'online'
    return 'offline'


def status_text(row):
    state = semantic_state(row)
    text = str(row.get('status') or row.get('connection') or tr('ref_no_signal'))
    if text == 'Online':
        text = row.get('connection') or tr('ref_connected')
    if row.get('errorCode') and str(row['errorCode']) not in text:
        text=tr('ref_error_code',code=row['errorCode'],text=text)
    # Drop a redundant prefix, not information about the observed state.
    text = re.sub(r'^BLOCK ACC\s*[:·-]?\s*', '', text, flags=re.I)
    symbols = {'online':'●', 'loading':'◌', 'block':'↻', 'offline':'○', 'error':'!'}
    return symbols[state] + '  ' + text[:1].upper() + text[1:]


def summary_text(total, active, queue, selected, errors):
    selection = tr('ref_selected_one') if selected == 1 else tr('ref_selected_many')
    error = tr('ref_error_one') if errors == 1 else tr('ref_error_many')
    return tr('ref_summary', total=total, active=active, queue=queue, selected=selected, selection=selection, errors=errors, error=error)


class NoticeSink:
    """Compatibility adapter for existing notice.config(text=...) call sites."""
    def __init__(self, owner): self.owner = owner
    def config(self, **kwargs):
        if 'text' in kwargs: self.owner.transient_status(kwargs['text'])
    configure = config


class RefinedUI:
    def init_refinement(self):
        self.refined = True
        self.fit_timer = None
        self.notice_timer = None
        self.status_message = ''
        self.user_widths = dict(self.ui_prefs.get('manualWidths', {}))
        self.table.bind('<Configure>', lambda event: self.schedule_fit(), add='+')
        self.table.bind('<ButtonPress-1>', self.column_press, add='+')
        self.table.bind('<ButtonRelease-1>', self.column_release, add='+')
        self.table.configure(xscrollcommand=self.horizontal_visibility)
        self.horizontal.pack_forget()
        # The old metrics and notice widgets remain available to legacy render calls,
        # but only the two new footer rows are mapped.
        self.metrics[0].master.pack_forget()
        self.statusbar.pack_forget()
        self.notice.pack_forget()
        self.notice = NoticeSink(self)
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Button) and child.cget('text') == tr('ui_871f24c4cdaf'):
                child.destroy()
        self.toolbar.pack_forget()
        self.footer_line = tk.Frame(self.toolbar.master, padx=2, pady=2)
        content = self.table.master.master.master
        self.footer_line.pack(side='bottom', fill='x', before=content)
        self.toolbar.pack(side='bottom', fill='x', pady=(4, 2), before=content)
        self.footer_selection.pack_forget()
        self.footer_summary = tk.Label(self.footer_line, anchor='w', font=(theme.FONT, 8))
        self.footer_line.columnconfigure(0,weight=1)
        self.footer_summary.grid(row=0,column=0,sticky='ew')
        self.footer_summary.bind('<Configure>',lambda event:self.footer_summary.config(wraplength=max(1,event.width-4)))
        self.chip_update = self.make_chip(self.footer_line, tr('ui_cfeb11c07f77'), self.updates)
        self.chip_update.grid(row=0,column=2,padx=(6,0))
        self.chip_diagnostic = self.make_chip(self.footer_line, tr('ui_040835e837a6'), self.diagnostic)
        self.chip_diagnostic.grid(row=0,column=1,padx=(6,0))
        self.header = tk.Frame(self.workspace, pady=2)
        self.header.pack(before=self.tabs, fill='x')
        self.brand_art = tk.Label(self.header)
        self.brand_art.pack(side='left', padx=(0, 5))
        self.version_chip = tk.Label(self.header, text=tr('ref_brand'), font=(theme.FONT, 8), anchor='w')
        self.version_chip.pack(side='left')
        # Utility/config actions live in their menus. Frequent actions remain here.
        self.tools_button.master.destroy()
        utilities=self.root.nametowidget(self.menubar.entrycget(1,'menu'))
        utilities.add_separator()
        utilities.add_command(label=tr('ui_ac1bfe35e71d'),command=self.show_search,accelerator='Ctrl+F')
        utilities.add_command(label=tr('ui_6fc2e4220f00'),command=lambda:self.run('/cancel',{}))
        self.profile_button.grid_remove()
        self.frequent_actions=tk.Frame(self.compact_panel)
        self.frequent_actions.grid(row=7,column=0,sticky='ew',pady=(3,0))
        self.profile_button=self.button(self.frequent_actions,tr('ui_c8e4eed80827'),self.toggle_controls)
        self.profile_button.pack(side='left',fill='x',expand=True,padx=(0,3))
        self.heartbeat_button=self.button(self.frequent_actions,tr('ui_eb4d4196e7cc'),self.heartbeat)
        self.heartbeat_button.pack(side='left',fill='x',expand=True)
        self.compact_panel.rowconfigure(5, weight=0)
        self.destination_error.grid(row=5, column=0, sticky='ew')
        self.progress_panel = tk.Frame(self.compact_panel)
        self.progress_panel.grid(row=6, column=0, sticky='ew', pady=(4, 2))
        self.progress_title = tk.Label(self.progress_panel, text=tr('ref_stage'), font=(theme.FONT, 8), anchor='w')
        # Inline caption keeps the stage readable without spending a second row.
        self.progress_text = tk.Label(self.progress_panel, font=(theme.FONT, 8), anchor='w', justify='left', wraplength=round(220*self.ui_scale))
        self.progress_text.pack(fill='x')
        self.progress_panel.bind('<Configure>',lambda event:self.progress_text.config(wraplength=max(1,event.width-2)))
        self.current_account.config(wraplength=round(220*self.ui_scale))
        self.current_account.grid_configure(pady=(3,2))
        self.recent_panel = tk.Frame(self.compact_panel)
        self.recent_panel.grid(row=9, column=0, sticky='nsew', pady=(4, 0))
        self.compact_panel.rowconfigure(9, weight=1)
        self.recent_title = tk.Label(self.recent_panel, text=tr('ref_recent'), font=(theme.FONT, 8), anchor='w')
        self.recent_title.grid(row=0, column=0, columnspan=2, sticky='w')
        self.recent_links = []
        for index in range(5):
            chip = self.make_chip(self.recent_panel, '', lambda i=index: self.select_recent(i), dot=False)
            chip.grid(row=1+index//2, column=index%2, sticky='w', padx=(0, 5))
            self.recent_links.append(chip)
        self.recent_empty = tk.Label(self.recent_panel, text=tr('ref_no_recent'), font=(theme.FONT, 8), anchor='w')
        self._recent_cache = None
        self.compact_status.grid_remove()  # Detail is in the stage panel; no duplicate row.
        self.table.heading('account', text=tr('ref_nick'))
        self.install_tooltip(self.footer_summary,lambda:self.status_message if self.status_message else '')
        self.install_tooltip(self.chip_update,lambda:tr('ref_last_check',time=self.last_check))
        self.style_refinement()
        self.render_refinement()
        self.validate_destination()

    def make_chip(self, parent, text, action, dot=True):
        label = tk.Label(parent, text=('●  ' if dot else '')+text, font=(theme.FONT, 8), cursor='hand2', takefocus=True, padx=3, pady=2, highlightthickness=1)
        label._sk_chip = True
        label._sk_dot = dot
        label._sk_text = text
        label._sk_level = 'info'
        label.bind('<Button-1>', lambda event: action())
        label.bind('<Return>', lambda event: action())
        label.bind('<space>', lambda event: (action(), 'break')[-1])
        label.bind('<FocusIn>', lambda event: label.config(highlightbackground=self.palette['accent']))
        label.bind('<FocusOut>', lambda event: label.config(highlightbackground=label.master.cget('bg')))
        label.bind('<Enter>', lambda event: label.config(font=(theme.FONT, 8, 'underline')))
        label.bind('<Leave>', lambda event: label.config(font=(theme.FONT, 8)))
        return label

    def style_refinement(self):
        if not getattr(self, 'refined', False): return
        p = self.palette
        self.footer_line.config(bg=p['alternate'])
        self.footer_summary.config(bg=p['alternate'], fg=p['muted'])
        self.header.config(bg=p['bg'])
        self.brand_art.config(bg=p['bg'])
        self.version_chip.config(bg=p['bg'], fg=p['muted'])
        self.compact_panel.config(bg=p['alternate'], bd=0, highlightthickness=1, highlightbackground=p['border'])
        for container in (self.progress_panel, self.recent_panel,self.frequent_actions): container.config(bg=p['alternate'])
        for label in (self.progress_title, self.recent_title, self.recent_empty): label.config(bg=p['alternate'], fg=p['muted'])
        self.progress_text.config(bg=p['alternate'], fg=p['info'])
        self.current_account.config(bg=p['alternate'])
        for chip in (self.chip_diagnostic, self.chip_update, *self.recent_links):
            bg=chip.master.cget('bg')
            chip.config(bg=bg, fg=p[chip._sk_level], highlightbackground=bg, highlightcolor=p['accent'])
        self.add_arrow.config(bg=p['button'],fg=p['text'],activebackground=p['hover'],activeforeground=p['text'],relief='flat',bd=0,pady=3,highlightthickness=1,highlightbackground=p['button'],highlightcolor=p['accent'],takefocus=True)
        self.table.master.config(highlightthickness=1,highlightbackground=p['border'],bd=0)
        self.table.configure(show='tree headings')
        self.table.column('#0', width=round(26*self.ui_scale), minwidth=round(26*self.ui_scale), stretch=False)
        for state, token in [('online','success'),('loading','info'),('block','warning'),('offline','muted'),('error','error')]:
            self.table.tag_configure(state, foreground=p[token])
        self.schedule_fit()

    def column_press(self, event):
        self._resizing_column = None
        if self.table.identify_region(event.x,event.y) == 'separator':
            name=self.table.identify_column(event.x)
            index=int(name[1:])-1
            columns=list(self.table['displaycolumns'])
            if 0 <= index < len(columns): self._resizing_column=columns[index]

    def column_release(self, event):
        column=getattr(self,'_resizing_column',None)
        if column:
            self.user_widths[column]=self.table.column(column,'width')/self.ui_scale
            self.ui_prefs['manualWidths']=dict(self.user_widths)
            self.persist_columns()
        self._resizing_column=None
        self.schedule_fit()

    def schedule_fit(self):
        if getattr(self,'fit_timer',None): self.root.after_cancel(self.fit_timer)
        self.fit_timer=self.root.after_idle(self.fit_columns)

    def fit_columns(self):
        self.fit_timer=None
        if not self.table.winfo_exists(): return
        font=tkfont.Font(root=self.root, font=ttk.Style(self.root).lookup('Treeview','font'))
        heading=tkfont.Font(root=self.root, font=ttk.Style(self.root).lookup('Treeview.Heading','font'))
        columns=list(self.table['displaycolumns'])
        widths={}
        for column in columns:
            values=[self.table.set(identity,column) for identity in self.table.get_children()]
            natural=max([heading.measure(self.table.heading(column,'text'))]+[font.measure(value) for value in values])+round(16*self.ui_scale)
            widths[column]=max(natural, round(self.user_widths.get(column,0)*self.ui_scale))
        available=max(1,self.table.winfo_width()-round(26*self.ui_scale)-2)
        # No artificial 145px Nick minimum: size from actual text. Status grows last.
        if 'status' in widths:
            other=sum(width for name,width in widths.items() if name!='status')
            widths['status']=max(round(heading.measure(self.table.heading('status','text'))+16*self.ui_scale),round(self.user_widths.get('status',0)*self.ui_scale),available-other)
        for column in columns:
            self.table.column(column,minwidth=1,stretch=False)
        for column,width in widths.items():
            self.table.column(column,width=width,minwidth=width,stretch=column=='status')
        self.root.after_idle(self.update_horizontal)

    def horizontal_visibility(self, first, last):
        self.horizontal.set(first,last)
        self.update_horizontal(float(first),float(last))

    def update_horizontal(self, first=None, last=None):
        if first is None: first,last=self.table.xview()
        total=self.table.column('#0','width')+sum(self.table.column(col,'width') for col in self.table['displaycolumns'])
        fits=total<=self.table.winfo_width()+2
        if fits or (first<=0.001 and last>=0.999):
            if self.horizontal.winfo_manager():self.horizontal.pack_forget()
        elif not self.horizontal.winfo_manager():
            self.horizontal.pack(side='bottom',fill='x')

    def transient_status(self, text):
        if self.notice_timer:self.root.after_cancel(self.notice_timer)
        self.status_message=str(text)
        self.render_footer()
        self.notice_timer=self.root.after(5000,self.clear_status_message)

    def clear_status_message(self):
        self.notice_timer=None
        self.status_message=''
        self.render_footer()

    def render_footer(self):
        if not getattr(self,'refined',False): return
        active=sum(row.get('age') is not None and row['age']<20 for row in self.rows.values())
        errors=sum(self.row_has_error(row) for row in self.rows.values())
        queue=self.state.get('waiting',0)
        summary=summary_text(len(self.rows),active,queue,len(self.ids()),errors)
        self.footer_summary.config(text=self.status_message or summary)
        warning=any(semantic_state(row) in ('block','loading','offline') for row in self.rows.values())
        self.chip_diagnostic._sk_level='error' if errors else 'warning' if warning else 'success' if self.rows else 'info'
        self.chip_diagnostic.config(fg=self.palette[self.chip_diagnostic._sk_level])

    def render_refinement(self):
        if not getattr(self,'refined',False): return
        self.render_footer()
        if self.rows and self.banner_text.cget('text')==tr('ui_5671c8725752'):
            self.banner.pack_forget()
        version=str(self.state.get('version','0.12.0'))
        version=re.sub(r'\s*UI preview\b','',version,flags=re.I)
        self.version_chip.config(text=tr('ref_version',version=version))
        ids=self.ids()
        row=self.rows.get(str(ids[0]),{}) if len(ids)==1 else {}
        status=str(row.get('status','')).casefold()
        connection=str(row.get('connection','')).casefold()
        if row.get('age') is not None and row['age']<20:
            observed=tr('ref_stage_confirmed')
        elif 'heartbeat' in status:
            observed=tr('ref_stage_heartbeat')
        elif 'protocolo' in status or 'launcher' in status:
            observed=tr('ref_stage_protocol')
        elif 'ticket' in status:
            observed=tr('ref_stage_ticket')
        elif 'sess' in status or 'autentic' in status:
            observed=tr('ref_stage_session')
        else:observed=tr('ref_stage_unknown')
        self.progress_text.config(text=tr('ref_stage_inline',stage=observed), fg=self.palette[{'online':'success','loading':'info','block':'warning','offline':'muted','error':'error'}[semantic_state(row)]])
        self.install_selection_detail(row)
        recent=tuple(self.ui_prefs.get('destinations',[])[:5])
        if recent!=self._recent_cache:
            self._recent_cache=recent
            for index,chip in enumerate(self.recent_links):
                if index<len(recent):chip.config(text=str(recent[index]));chip.grid()
                else:chip.grid_remove()
            if recent:self.recent_empty.grid_remove()
            else:self.recent_empty.grid(row=1,column=0,columnspan=2,sticky='w')
        self.schedule_fit()

    def install_selection_detail(self,row):
        # Full observed status is available without claiming unreported stages.
        if not row:self.progress_text.config(text=tr('ref_stage_inline',stage=tr('ref_select_account')))

    def select_recent(self,index):
        recent=self.ui_prefs.get('destinations',[])[:5]
        if index<len(recent):
            self.place.delete(0,'end');self.place.insert(0,str(recent[index]));self.validate_destination()

    def refinement_icons_ready(self):
        image=self.icons.get('brand')
        if image:
            factor=max(1,round(image.width()/(18*self.ui_scale)))
            self.brand_thumbnail=image.subsample(factor,factor)
            self.brand_art.config(image=self.brand_thumbnail)

    def truncated_cell(self,event):
        identity=self.table.identify_row(event.y)
        column=self.table.identify_column(event.x)
        if not identity or column in ('','#0'): return ''
        columns=list(self.table['displaycolumns'])
        index=int(column[1:])-1
        if not 0<=index<len(columns):return ''
        value=self.table.set(identity,columns[index])
        font=tkfont.Font(root=self.root,font=ttk.Style(self.root).lookup('Treeview','font'))
        box=self.table.bbox(identity,column)
        return value if box and font.measure(value)+12*self.ui_scale>box[2] else ''

    def render_update_chip(self,value=None,error=None):
        if not getattr(self,'refined',False):return
        level='error' if error else 'warning' if (value or {}).get('newer') else 'success'
        self.chip_update._sk_level=level
        self.chip_update.config(fg=self.palette[level])

"""Offline Indian 13-card Rummy: one human vs three computer opponents.
Pure Tkinter; no network, accounts, betting, or external dependencies.
"""
import tkinter as tk
from tkinter import messagebox
import random, itertools, copy

SUITS = ['♠','♥','♦','♣']
SUIT_ORDER = {s:i for i,s in enumerate(SUITS)}
RED = {'♥','♦'}
RANKS = range(1,14)
RANK_LABEL = {1:'A',11:'J',12:'Q',13:'K'}
BG='#E8EDF2'; PANEL='#FFFFFF'; PANEL2='#DCA0BA'; GOLD='#4B1742'; WHITE='#FFFFFF'; MUTED='#3F3440'; DARK='#201820'; REDTXT='#B51F48'

def rt(r): return RANK_LABEL.get(r,str(r))
def ct(c): return f'{rt(c[0])}{c[1]}'
def card_sort(c): return (SUIT_ORDER[c[1]], 14 if c[0]==1 else c[0])
def new_deck():
    # Two decks for four-player Indian Rummy; each card instance has unique id.
    return ([(r,s,d) for d in range(2) for s in SUITS for r in RANKS]
            + [('JOKER','★',j) for j in range(4)])
def card_rank(c): return c[0]
def card_suit(c): return c[1]
def is_joker(c,wild_rank): return c[0]=='JOKER' or c[0]==wild_rank

def group_kind(cards, wild_rank):
    """Classify a legal 3/4-card Indian Rummy meld.

    Rules used by this game:
    - Pure sequence: 3/4 consecutive natural cards, same suit; printed jokers
      are forbidden. A wild-rank card may be used at its printed identity.
    - Impure sequence: 3/4 cards in one suit-run, with one or more jokers
      filling missing ranks. At least one non-joker natural card is required.
    - Set: 3/4 cards of the same rank, with different suits for natural cards;
      jokers may fill missing suit slots.
    """
    if len(cards) not in (3, 4):
        return None

    printed = [c for c in cards if c[0] == 'JOKER']
    wilds = [c for c in cards if is_joker(c, wild_rank)]
    fixed = [c for c in cards if not is_joker(c, wild_rank)]

    # Test sequence rank values with Ace low (A-2-3-4) and high (J-Q-K-A).
    def consecutive(values, size):
        if len(values) != size or len(set(values)) != size:
            return False
        ordered = sorted(values)
        return ordered == list(range(ordered[0], ordered[0] + size))

    # Pure sequence: all physical cards natural, one suit, exact consecutive run.
    if not printed and len({c[1] for c in cards}) == 1:
        ranks = [c[0] for c in cards]
        if all(isinstance(r, int) for r in ranks):
            low_values = [1 if r == 1 else r for r in ranks]
            high_values = [14 if r == 1 else r for r in ranks]
            if consecutive(low_values, len(cards)) or consecutive(high_values, len(cards)):
                return 'pure'

    # Impure sequence: at least one natural fixed card anchors suit and run.
    # Wild-rank cards and printed jokers can occupy missing rank positions.
    if fixed and len({c[1] for c in fixed}) == 1:
        raw = [c[0] for c in fixed]
        if all(isinstance(r, int) for r in raw):
            if len(set(raw)) == len(raw):
                variants = [[14 if r == 1 else r for r in raw]]
                if 1 in raw:
                    variants.append([1 if r == 1 else r for r in raw])
                for vals in variants:
                    for run_start in range(1, 15 - len(cards) + 1):
                        run = set(range(run_start, run_start + len(cards)))
                        if all(v in run for v in vals) and len(run - set(vals)) == len(wilds):
                            return 'impure'

    # Set: natural cards must share rank and have distinct suits.
    # Wildcards fill the remaining suit slots; duplicate physical suits
    # among natural cards are not allowed.
    if fixed and len({c[0] for c in fixed}) == 1 and len({c[1] for c in fixed}) == len(fixed):
        if len(fixed) + len(wilds) == len(cards) and len(cards) <= 4:
            return 'set'
    if len(wilds) == len(cards):
        # All-joker groups are useful as a set, but cannot form a sequence.
        return 'set'
    return None

def valid_declaration(hand,wild_rank):
    if len(hand)!=13: return False
    n=len(hand); groups=[]
    for size in (3,4):
        for inds in itertools.combinations(range(n),size):
            kind=group_kind([hand[i] for i in inds],wild_rank)
            if kind: groups.append((sum(1<<i for i in inds),kind))
    by_first={i:[] for i in range(n)}
    for mask,kind in groups:
        for i in range(n):
            if mask>>i&1: by_first[i].append((mask,kind))
    full=(1<<n)-1; memo={}
    def solve(mask,seqs,pure):
        if mask==full: return seqs>=2 and pure
        key=(mask,seqs,pure)
        if key in memo: return memo[key]
        rem=full^mask; first=next(i for i in range(n) if rem>>i&1)
        for gm,kind in by_first[first]:
            if gm&mask: continue
            if solve(mask|gm,seqs+int(kind in ('pure','impure')),pure or kind=='pure'):
                memo[key]=True; return True
        memo[key]=False; return False
    return solve(0,0,False)

def points(c,wild_rank):
    if is_joker(c,wild_rank): return 0
    r=c[0]
    return 10 if r in (1,11,12,13) else r

def hand_score(hand,wild_rank):
    """Penalty for a non-winner: minimize unmatched points, requiring a pure meld.

    If no pure sequence can be made, the full hand penalty applies. Otherwise,
    valid melds are removed from the penalty and only unmatched cards count.
    """
    if len(hand) != 13:
        return min(80, sum(points(c, wild_rank) for c in hand))
    melds=[]
    for size in (3,4):
        for inds in itertools.combinations(range(13), size):
            cards=[hand[i] for i in inds]
            kind=group_kind(cards,wild_rank)
            if kind:
                mask=sum(1<<i for i in inds)
                melds.append((mask,kind))
    by_first={i:[] for i in range(13)}
    for mask,kind in melds:
        for i in range(13):
            if mask>>i & 1: by_first[i].append((mask,kind))
    full=(1<<13)-1
    values=[points(c,wild_rank) for c in hand]
    memo={}
    def solve(mask,has_pure):
        key=(mask,has_pure)
        if key in memo: return memo[key]
        if mask==full:
            return (0, has_pure)
        i=next(i for i in range(13) if not (mask>>i&1))
        # Option 1: this card remains unmatched.
        best_penalty, best_pure=solve(mask|(1<<i),has_pure)
        best=(best_penalty+values[i],best_pure)
        # Option 2: place a valid meld containing this card.
        for gm,kind in by_first[i]:
            if gm&mask: continue
            result=solve(mask|gm,has_pure or kind=='pure')
            if result[1] and result[0] < best[0]: best=result
        memo[key]=best
        return best
    penalty,pure=solve(0,False)
    if not pure:
        penalty=sum(values)
    return min(80,penalty)

class RummyApp:
    def __init__(self,root):
        self.root=root
        # Normalize Tk's logical-pixel scaling BEFORE creating any widgets.
        # On Android/Pydroid some builds report physical screen dimensions while
        # also applying a large Tk scaling factor. That combination makes even
        # small fonts render huge and pushes labels over buttons (touches then
        # appear not to work). Use pixel-sized fonts and one consistent scale.
        self.root.title('Offline Indian Rummy'); self.root.configure(bg=BG)
        try:
            self.root.tk.call('tk', 'scaling', 1.0)
        except Exception:
            pass
        try:
            self.root.update_idletasks()
        except Exception:
            pass
        # Keep the original V27 window-manager approach for compatibility.
        # On this user's Android Tk build, forcing overrideredirect(True) may
        # cause the window to disappear; let the app window manager handle it.
        self.screen_w = max(320, int(root.winfo_screenwidth()))
        self.screen_h = max(480, int(root.winfo_screenheight()))
        try:
            root.resizable(False, False)
            root.state('normal')
            root.attributes('-fullscreen', True)
            root.after(120, lambda: self._apply_fullscreen_mode())
        except Exception:
            pass
        root.bind('<Escape>', self._exit_fullscreen)
        root.bind('<F11>', self._toggle_fullscreen)
        self.difficulty='Normal'; self.scores=[0,0,0,0]; self.opponent_count=3; self.names=['You','Computer 1','Computer 2','Computer 3']; self.round_no=0; self.busy=False
        self.sound_enabled = True
        self.show_menu()
    def _apply_fullscreen_mode(self):
        try:
            self.root.resizable(False, False)
            self.root.attributes('-fullscreen', True)
        except Exception:
            pass

    def _exit_fullscreen(self, event=None):
        try:
            self.root.attributes('-fullscreen', False)
            self.root.state('normal')
            self.root.resizable(False, False)
        except Exception:
            pass

    def _toggle_fullscreen(self, event=None):
        try:
            current = bool(self.root.attributes('-fullscreen'))
            self.root.attributes('-fullscreen', not current)
            self.root.resizable(False, False)
        except Exception:
            pass

    def pink_frame(self, parent):
        """Light-pink frame decorated with tiny red roses and dew drops."""
        frame = tk.Frame(parent, bg=BG, bd=0, highlightthickness=0)
        # Small rose + dew-drop motifs sit behind the controls, leaving text readable.
        # Use native Unicode emoji/text so the game remains fully offline.
        for row, y in enumerate((0.055, 0.17, 0.285, 0.40, 0.515, 0.63, 0.745, 0.86, 0.975)):
            for col, x in enumerate((0.025, 0.145, 0.265, 0.385, 0.505, 0.625, 0.745, 0.865, 0.975)):
                xx = min(0.985, max(0.015, x + (0.035 if row % 2 else 0)))
                motif = tk.Label(
                    frame, text='', bg=BG, fg='#C2183A',
                    font=('Segoe UI Emoji', 8 if (row + col) % 2 else 9),
                    bd=0, padx=0, pady=0
                )
                motif.place(relx=xx, rely=y, anchor='center')
                motif.lower()
        return frame

    def clear(self):
        for w in self.root.winfo_children(): w.destroy()
    def btn(self,parent,text,cmd,bg=GOLD,fg=WHITE,size=13,**kw):
        # Build options first so callers can safely override activebackground,
        # padx, pady, etc. without duplicate-keyword errors on Android Tk.
        options = {
            'bg': bg,
            'fg': fg,
            'activebackground': '#E7B4D2',
            'activeforeground': DARK,
            'font': ('Arial', -abs(int(size)), 'bold'),
            'relief': 'flat',
            'bd': 0,
            'cursor': 'hand2',
            'padx': 12,
            'pady': 10,
        }
        options.update(kw)
        return tk.Button(parent, text=text, command=cmd, **options)
    def title(self,parent,text,size=20,color=GOLD): tk.Label(parent,text=text,font=('Arial', -(size),'bold'),bg=parent['bg'],fg=color).pack(pady=5)
    def play_sound(self, kind='tap'):
        """Short offline UI tones, with a Tk bell fallback."""
        if not getattr(self, 'sound_enabled', True):
            return
        try:
            import winsound
            tones = {'tap': (720, 45), 'sort': (880, 65), 'draw': (620, 70), 'discard': (520, 75), 'win': (990, 120)}
            freq, duration = tones.get(kind, tones['tap'])
            winsound.Beep(freq, duration)
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass

    def toggle_sound(self):
        self.sound_enabled = not getattr(self, 'sound_enabled', True)
        try:
            self.sound_button.config(text='🔊 SOUND: ON' if self.sound_enabled else '🔇 SOUND: OFF', bg='#238636' if self.sound_enabled else '#64748B')
        except Exception:
            pass
        if self.sound_enabled:
            self.play_sound('tap')

    def show_menu(self):
        self.clear()
        outer=tk.Frame(self.root,bg=BG,bd=0,highlightthickness=0)
        outer.pack(fill='both',expand=True,padx=8,pady=8)
        f=tk.Frame(outer,bg=BG,bd=0,highlightthickness=0)
        f.place(relx=0.5,rely=0.5,anchor='center',relwidth=1.0)
        # IMPORTANT: On some Android/Pydroid Tk builds screenwidth is reported
        # in physical pixels while Tk fonts are also DPI-scaled. Using sw/22
        # therefore made the title enormous and caused every line to clip.
        # Use the realised window width where possible and conservative absolute
        # pixel font sizes (negative Tk sizes) with hard caps for phone displays.
        try:
            self.root.update_idletasks()
            viewport_w = self.root.winfo_width()
            if viewport_w < 100:
                viewport_w = self.root.winfo_screenwidth()
        except Exception:
            viewport_w = self.root.winfo_screenwidth()
        sw = max(300, min(900, int(viewport_w)))
        title_size = max(31, min(43, int(sw * 0.060)))
        subtitle_size = max(24, min(32, int(sw * 0.046)))
        body_size = max(20, min(27, int(sw * 0.038)))
        button_size = max(25, min(33, int(sw * 0.046)))
        wrap = max(220, min(900, int(sw * 0.92)))
        # Main heading: two large, centered lines as requested.
        tk.Label(f,text='INDIAN PROFESSIONAL RUMMY',font=('Arial', -(title_size),'bold'),bg=BG,fg=GOLD,anchor='center',justify='center',wraplength=wrap).pack(fill='x',padx=5,pady=(10,2))
        tk.Label(f,text='Powered by Python',font=('Arial', -(subtitle_size),'bold'),bg=BG,fg=DARK,anchor='center',justify='center').pack(fill='x',padx=8,pady=(2,8))
        tk.Label(f,text='Created by @cd786hassan',font=('Arial', -max(17, min(23, int(sw*0.032))),'bold'),bg=BG,fg='#7B174F',anchor='center').pack(fill='x',padx=8,pady=(0,6))
        tk.Label(f,text='13-Card • Offline • You vs 1, 2 or 3 Computers',font=('Arial', -(body_size),'bold'),bg=BG,fg=DARK,wraplength=wrap,justify='center').pack(fill='x',padx=8,pady=(3,8))
        tk.Label(f,text='Your cards stay private. All computer hands remain hidden.',font=('Arial',-(body_size),'bold'),bg=BG,fg=MUTED,wraplength=wrap,justify='center').pack(fill='x',padx=8,pady=(2,12))
        self.btn(f,'PLAY GAME',self.setup,bg='#238636',size=button_size).pack(fill='x',padx=4,pady=6,ipady=16)
        self.btn(f,'HOW TO PLAY',self.rules,bg=PANEL2,fg=DARK,size=max(22,button_size-2)).pack(fill='x',padx=4,pady=6,ipady=14)
        self.btn(f,'SCOREBOARD',self.scoreboard,bg='#FFF0F5',fg=GOLD,size=max(22,button_size-2)).pack(fill='x',padx=4,pady=6,ipady=14)
        self.sound_button = self.btn(f,'🔊 SOUND: ON',self.toggle_sound,bg='#238636',fg=WHITE,size=max(20,button_size-4))
        self.sound_button.pack(fill='x',padx=4,pady=5,ipady=8)
        tk.Label(f,text='No internet • No account • No real-money play',font=('Arial', -max(19, min(25, int(sw/30))),'bold'),bg=BG,fg=MUTED,wraplength=wrap,justify='center').pack(fill='x',padx=8,pady=(10,10))
    def setup(self):
        """New Game screen styled to match the supplied blue/green reference."""
        self.clear()
        # Keep this screen independent from the pink decorative frame used elsewhere.
        outer=tk.Frame(self.root,bg='#EEF2F7',bd=0,highlightthickness=0)
        outer.pack(fill='both',expand=True,padx=7,pady=7)
        f=tk.Frame(outer,bg='#EEF2F7',bd=0,highlightthickness=0)
        f.place(relx=0.5,rely=0.5,anchor='center',relwidth=1.0)
        try:
            self.root.update_idletasks()
            sw=max(300,min(900,int(self.root.winfo_width() if self.root.winfo_width()>100 else self.root.winfo_screenwidth())))
            sh=max(480,int(self.root.winfo_height() if self.root.winfo_height()>100 else self.root.winfo_screenheight()))
        except Exception:
            sw=max(300,min(900,int(self.root.winfo_screenwidth()))); sh=max(480,int(self.root.winfo_screenheight()))
        compact=sh < 700
        title_size=max(25,min(46,int(sw*.075)))
        head_size=max(15,min(25,int(sw*.045)))
        name_size=max(15,min(25,int(sw*.043)))
        detail_size=max(12,min(20,int(sw*.032)))
        row_pad=3 if compact else 5
        inner_pad=4 if compact else 7

        # Navy title bar with playing-card suit ornaments.
        titlebar=tk.Frame(f,bg='#073568',highlightthickness=2,highlightbackground='#D8B65A')
        titlebar.pack(fill='x',pady=(0,5))
        titlebar.grid_columnconfigure(1,weight=1)
        tk.Label(titlebar,text='♠',font=('Arial',-max(22,title_size),'bold'),bg='#073568',fg='#F4D77C').grid(row=0,column=0,padx=(10,3),pady=2)
        tk.Label(titlebar,text='NEW GAME',font=('Georgia',-title_size,'bold'),bg='#073568',fg='#FFE8A0').grid(row=0,column=1,sticky='ew',pady=2)
        tk.Label(titlebar,text='♥',font=('Arial',-max(22,title_size),'bold'),bg='#073568',fg='#E64B5D').grid(row=0,column=2,padx=(3,10),pady=2)

        def section(text,bg,fg,symbol):
            bar=tk.Frame(f,bg=bg,highlightthickness=1,highlightbackground='#B9C7D7')
            bar.pack(fill='x',pady=(3,3))
            bar.grid_columnconfigure(1,weight=1)
            tk.Label(bar,text=symbol,font=('Arial',-max(18,head_size),'bold'),bg=bg,fg='#FFFFFF').grid(row=0,column=0,padx=(10,4),pady=3)
            tk.Label(bar,text=text.upper(),font=('Arial',-head_size,'bold'),bg=bg,fg=fg,anchor='center').grid(row=0,column=1,sticky='ew',pady=5)
            tk.Label(bar,text=symbol,font=('Arial',-max(18,head_size),'bold'),bg=bg,fg='#FFFFFF').grid(row=0,column=2,padx=(4,10),pady=3)

        section('PLAYER SELECTION','#07508C','#FFFFFF','♠')
        self.opponents_var=tk.IntVar(value=getattr(self,'opponent_count',3))
        self.opponent_rows=[]
        for count,desc,people in [(1,'2 players total','♟♟'),(2,'3 players total','♟♟♟'),(3,'4 players total','♟♟♟♟')]:
            row=tk.Frame(f,bg='#F5F7FA',highlightthickness=2,highlightbackground='#C6D0DC')
            row.pack(fill='x',padx=2,pady=row_pad)
            row.grid_columnconfigure(1,weight=1)
            rb=tk.Radiobutton(row,text='',variable=self.opponents_var,value=count,command=self._update_opponent_selection,
                bg='#F5F7FA',activebackground='#D6E9FF',selectcolor='#FFFFFF',indicatoron=True,
                highlightthickness=0,bd=0,takefocus=False)
            rb.grid(row=0,column=0,rowspan=2,padx=(8,5),pady=inner_pad)
            tk.Label(row,text=f'{count} Computer'+('' if count==1 else 's'),font=('Arial',-name_size,'bold'),bg='#F5F7FA',fg='#102D52',anchor='w').grid(row=0,column=1,sticky='sw',padx=2,pady=(inner_pad,0))
            tk.Label(row,text=desc,font=('Arial',-detail_size),bg='#F5F7FA',fg='#40516A',anchor='w').grid(row=1,column=1,sticky='nw',padx=2,pady=(0,inner_pad))
            tk.Label(row,text=people,font=('Arial',-max(19,detail_size+4),'bold'),bg='#F5F7FA',fg='#8793A4').grid(row=0,column=2,rowspan=2,padx=(4,12))
            self.opponent_rows.append((row,rb,count))
            def choose_opponents(event=None, value=count):
                self.opponents_var.set(value)
                self._update_opponent_selection()
            for widget in (row, rb) + tuple(row.winfo_children()):
                widget.bind('<Button-1>', choose_opponents)

        section('PLAYER MODE','#006B50','#FFFFFF','♣')
        self.diff=tk.StringVar(value=getattr(self,'difficulty','Normal'))
        self.difficulty_rows=[]
        for d,desc,bars in [('Easy','Relaxed choices','▰ ▱ ▱'),('Normal','Balanced opponents','▰ ▰ ▱'),('Hard','Careful card choices','▰ ▰ ▰')]:
            row=tk.Frame(f,bg='#F1F8F5',highlightthickness=2,highlightbackground='#B8D5CB')
            row.pack(fill='x',padx=2,pady=row_pad)
            row.grid_columnconfigure(1,weight=1)
            rb=tk.Radiobutton(row,text='',variable=self.diff,value=d,command=self._update_difficulty_selection,
                bg='#F1F8F5',activebackground='#D3F3E6',selectcolor='#FFFFFF',indicatoron=True,
                highlightthickness=0,bd=0,takefocus=False)
            rb.grid(row=0,column=0,rowspan=2,padx=(8,5),pady=inner_pad)
            tk.Label(row,text=d,font=('Arial',-name_size,'bold'),bg='#F1F8F5',fg='#063D31',anchor='w').grid(row=0,column=1,sticky='sw',padx=2,pady=(inner_pad,0))
            tk.Label(row,text=desc,font=('Arial',-detail_size),bg='#F1F8F5',fg='#345B53',anchor='w').grid(row=1,column=1,sticky='nw',padx=2,pady=(0,inner_pad))
            tk.Label(row,text=bars,font=('Arial',-max(16,detail_size+2),'bold'),bg='#F1F8F5',fg='#079B6A' if d!='Hard' else '#64748B').grid(row=0,column=2,rowspan=2,padx=(4,12))
            self.difficulty_rows.append((row,rb,d))
            def choose_difficulty(event=None, value=d):
                self.diff.set(value)
                self._update_difficulty_selection()
            for widget in (row, rb) + tuple(row.winfo_children()):
                widget.bind('<Button-1>', choose_difficulty)

        self._update_opponent_selection(); self._update_difficulty_selection()
        self.start_btn=self.btn(f,'▶   START GAME',self.start_game,bg='#00875F',fg='#FFFFFF',size=max(19,min(28,int(sw*.052)),),anchor='center',justify='center',pady=12,highlightthickness=3,highlightbackground='#E8C84C',activebackground='#00A778')
        self.start_btn.pack(fill='x',padx=3,pady=(6,4),ipady=5)
        self.btn(f,'⬅   BACK',self.show_menu,bg='#06447D',fg='#FFFFFF',size=max(17,min(25,int(sw*.045))),anchor='center',justify='center',pady=9,activebackground='#0C5A9D').pack(fill='x',padx=3,pady=(2,3),ipady=3)

    def _update_opponent_selection(self):
        selected=self.opponents_var.get()
        for row,rb,value in self.opponent_rows:
            active=value==selected
            bg='#BBD9FA' if active else '#F5F7FA'
            row.configure(bg=bg, highlightbackground='#087BE0' if active else '#C6D0DC')
            rb.configure(bg=bg, activebackground=bg, fg='#0756A5', selectcolor='#FFFFFF')
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=bg)
                    if child.grid_info().get('column') == 1:
                        child.configure(fg='#102D52' if child.grid_info().get('row')==0 else '#274B70')
                    else:
                        child.configure(fg='#0756A5' if active else '#8793A4')

    def _update_difficulty_selection(self):
        selected=self.diff.get()
        for row,rb,value in self.difficulty_rows:
            active=value==selected
            bg='#B9EEDB' if active else '#F1F8F5'
            row.configure(bg=bg, highlightbackground='#079B63' if active else '#B8D5CB')
            rb.configure(bg=bg, activebackground=bg, fg='#00885C', selectcolor='#FFFFFF')
            for child in row.winfo_children():
                if isinstance(child, tk.Label):
                    child.configure(bg=bg)
                    if child.grid_info().get('column') == 1:
                        child.configure(fg='#063D31' if child.grid_info().get('row')==0 else '#345B53')
                    else:
                        child.configure(fg='#079B6A' if active else '#64748B')

    def rules(self):
        """Large, centered How To Play page matching the enlarged home screen."""
        self.clear()
        outer=tk.Frame(self.root,bg=BG,bd=0,highlightthickness=0)
        outer.pack(fill='both',expand=True,padx=8,pady=8)
        f=tk.Frame(outer,bg=BG,bd=0,highlightthickness=0)
        f.place(relx=0.5,rely=0.5,anchor='center',relwidth=1.0,relheight=0.94)
        try:
            self.root.update_idletasks()
            sw=max(300,min(900,int(self.root.winfo_width() if self.root.winfo_width()>100 else self.root.winfo_screenwidth())))
        except Exception:
            sw=max(300,min(900,int(self.root.winfo_screenwidth())))
        title_size=max(28,min(38,int(sw*.052)))
        body_size=max(17,min(23,int(sw*.031)))
        self.title(f,'HOW TO PLAY',title_size,color=GOLD)
        text=('INDIAN 13-CARD RUMMY\n\n'
              '• Choose 1, 2 or 3 computer opponents (2 to 4 players total).\n'
              '• Each player starts with 13 cards. On your turn, draw one card from Stock or the top of Discard, then discard one card.\n'
              '• A valid declaration uses all 13 cards in groups, with at least TWO sequences and at least ONE PURE sequence.\n'
              '• Pure sequence: 3+ consecutive cards of the same suit, no joker substitution.\n'
              '• Impure sequence: a same-suit run completed with a joker. Set: 3 or 4 cards of the same rank in different suits.\n'
              '• Printed jokers and the selected wild rank can substitute in impure sequences/sets. This version treats wild-rank cards as jokers.\n'
              '• A valid declaration wins the round. Other players receive penalty points; winner gets 0. Penalty is capped at 80.\n'
              '• A wrong declaration is rejected. If stock runs out and cannot be rebuilt, the round ends and penalties are scored. This is a casual offline implementation; scoring and some house rules may differ from apps.')
        panel=tk.Frame(f,bg='#FFFFFF',highlightthickness=2,highlightbackground=GOLD,bd=0)
        panel.pack(fill='both',expand=True,padx=3,pady=(8,10))
        tk.Label(panel,text=text,font=('Arial',-body_size,'bold'),bg='#FFFFFF',fg=DARK,justify='left',anchor='nw',wraplength=max(240,int(sw*.91)),padx=14,pady=14).pack(fill='both',expand=True)
        self.btn(f,'⬅   BACK',self.show_menu,bg='#06447D',fg=WHITE,size=max(20,min(27,int(sw*.038)))).pack(fill='x',padx=3,pady=(2,3),ipady=12)

    def scoreboard(self):
        """Large, centered Scoreboard page matching the enlarged home screen."""
        self.clear()
        outer=tk.Frame(self.root,bg=BG,bd=0,highlightthickness=0)
        outer.pack(fill='both',expand=True,padx=8,pady=8)
        f=tk.Frame(outer,bg=BG,bd=0,highlightthickness=0)
        f.place(relx=0.5,rely=0.5,anchor='center',relwidth=1.0)
        try:
            self.root.update_idletasks()
            sw=max(300,min(900,int(self.root.winfo_width() if self.root.winfo_width()>100 else self.root.winfo_screenwidth())))
        except Exception:
            sw=max(300,min(900,int(self.root.winfo_screenwidth())))
        title_size=max(28,min(38,int(sw*.052)))
        row_size=max(20,min(27,int(sw*.038)))
        self.title(f,'SCOREBOARD',title_size,color=GOLD)
        panel=tk.Frame(f,bg=BG,bd=0,highlightthickness=0)
        panel.pack(fill='x',expand=False,pady=(8,10))
        for i,n in enumerate(getattr(self,'names',['You','Computer 1','Computer 2','Computer 3'])):
            tile=tk.Frame(panel,bg='#FFFFFF',highlightthickness=2,highlightbackground=GOLD,bd=0)
            tile.pack(fill='x',padx=3,pady=6)
            tk.Label(tile,text=f'{n}: {self.scores[i]} penalty points',font=('Arial',-row_size,'bold'),bg='#FFFFFF',fg=DARK,padx=12,pady=16,wraplength=max(240,int(sw*.9)),justify='center').pack(fill='x')
        self.btn(f,'⬅   BACK TO MENU',self.show_menu,bg='#06447D',fg=WHITE,size=max(20,min(27,int(sw*.038)))).pack(fill='x',padx=3,pady=(8,3),ipady=12)
    def start_game(self):
        # A new round has a different hand: never carry the previous round's
        # cached Sort Cards layout/group signature into it.
        self._sorted_group_cache = None
        self._sorted_group_cache_signature = None
        self.difficulty=self.diff.get(); self.opponent_count=int(self.opponents_var.get()); self.round_no+=1; self.names=['You']+[f'Computer {i}' for i in range(1,self.opponent_count+1)]
        deck=new_deck(); random.shuffle(deck); self.wild_rank=random.randint(1,13)
        self.hands=[[] for _ in range(self.opponent_count+1)]
        for _ in range(13):
            for h in self.hands: h.append(deck.pop())
        self.stock=deck; self.discard=[self.stock.pop()]
        self.discard_history=[('OPENING', ct(self.discard[-1]))]
        self._round_scored=False; self.turn=0; self.has_drawn=False; self.selected=None; self.joker_place_index=None; self.joker_place_options={}; self.game_over=False; self.busy=False; self.turn_no=0; self.undo_state=None; self.computer_after_id=None; self.last_message='Your turn: draw a card.'; self.max_turns=300
        self.render()
    def render(self):
        self.clear(); outer=self.pink_frame(self.root); outer.pack(fill='both',expand=True,padx=3,pady=3)
        top=self.pink_frame(outer); top.pack(fill='x', pady=(8,5))
        # Full-width royal title banner with high contrast and a separate subtitle strip.
        title_wrap=tk.Frame(top,bg='#263653',highlightthickness=3,highlightbackground='#D7AE45',bd=0)
        title_wrap.pack(fill='x',expand=True,padx=2,pady=(7,11))
        title_main=tk.Frame(title_wrap,bg='#263653',bd=0)
        title_main.pack(fill='x',expand=True,padx=3,pady=(10,7))
        tk.Label(title_main,text='♠  INDIAN PROFESSIONAL RUMMY  ♠',font=('Arial', -29,'bold'),bg='#263653',fg='#FFE08A',anchor='center',justify='center',wraplength=max(280,int((self.root.winfo_width() or self.root.winfo_screenwidth())*.94))).pack(fill='x',padx=4,pady=(3,5))
        subtitle=tk.Frame(title_wrap,bg='#F4E7C7',bd=0)
        subtitle.pack(fill='x',padx=2,pady=(0,2))
        tk.Label(subtitle,text='✦  POWERED BY PYTHON  ✦',font=('Arial', -17,'bold'),bg='#F4E7C7',fg='#263653',anchor='center').pack(fill='x',pady=(5,7))
        tk.Label(title_wrap,text='Created by @cd786hassan',font=('Arial', -13,'bold'),bg='#263653',fg='#FFE08A',anchor='center').pack(fill='x',pady=(0,5))
        tk.Label(outer,text=f'WILD JOKER: {rt(self.wild_rank)}  •  ROUND {self.round_no}  •  TURN {self.turn_no+1}',font=('Arial', -(20),'bold'),bg=BG,fg=DARK).pack(pady=(4,7), ipady=5)
        self.status=tk.Label(outer,text=self.last_message,font=('Arial', -(22),'bold'),bg=BG,fg=GOLD,wraplength=max(260, int((self.root.winfo_width() or self.root.winfo_screenwidth())*0.88))); self.status.pack(pady=(4,8), ipady=6)
        info=self.pink_frame(outer); info.pack(fill='x',pady=2)
        # Four high-contrast player report tiles, with a taller two-line layout.
        for i in range(1,len(self.hands)):
            tile=tk.Frame(info,bg='#D7EAF7',highlightthickness=2,highlightbackground='#174A70')
            tile.pack(side='left',expand=True,fill='x',padx=2)
            tk.Label(tile,text=f'♟ CPU {i}',font=('Arial', -18,'bold'),bg='#174A70',fg='#FFFFFF',padx=2,pady=10).pack(fill='x')
            tk.Label(tile,text=f'{len(self.hands[i])} cards\n{self.scores[i]} pts',font=('Arial', -16,'bold'),bg='#D7EAF7',fg='#102D40',padx=1,pady=10).pack(fill='x')
        you_tile=tk.Frame(info,bg='#D8F0E5',highlightthickness=2,highlightbackground='#17634E')
        you_tile.pack(side='left',expand=True,fill='x',padx=2)
        tk.Label(you_tile,text='YOU',font=('Arial', -19,'bold'),bg='#17634E',fg='#FFFFFF',padx=2,pady=10).pack(fill='x')
        tk.Label(you_tile,text=f'{len(self.hands[0])} cards\n{self.scores[0]} pts',font=('Arial', -16,'bold'),bg='#D8F0E5',fg='#103D30',padx=1,pady=10).pack(fill='x')
        # Stock count is shown on the DRAW STOCK action; the separate Stock/Discard boxes are removed.
        self.hand_area=tk.Frame(outer,bg='#FFFFFF',highlightbackground='#766575',highlightthickness=2); self.hand_area.pack(fill='x',expand=False,pady=(2,0))
        # A clean white breathing gap separates the hand board from history.
        self.history_gap=tk.Frame(outer,bg='#FFFFFF',height=12)
        self.history_gap.pack(fill='x',padx=4,pady=0)
        self.history_gap.pack_propagate(False)
        # Shared visible waste/discard history between the card board and action buttons.
        self.waste_box=tk.Frame(outer,bg='#FFFFFF',highlightbackground='#FFFFFF',highlightthickness=1)
        self.waste_box.pack(fill='x',padx=4,pady=(0,0))
        self.actions=self.pink_frame(outer); self.actions.pack(fill='both',expand=True,pady=(0,2))
        self.refresh_hand()
    def refresh_hand(self):
        for w in self.hand_area.winfo_children(): w.destroy()
        for w in self.actions.winfo_children(): w.destroy()
        for w in self.waste_box.winfo_children(): w.destroy()
        # Five equal history slots: CPU-1, CPU-2, CPU-3, YOU and the waste icon.
        # Recent cards are arranged left-to-right; the icon triggers DISCARD SELECTED.
        history_row = tk.Frame(self.waste_box, bg='#FFFFFF')
        history_row.pack(fill='both', expand=True, padx=3, pady=3)
        recent = list(reversed(self.discard_history[-4:]))
        for col in range(5):
            history_row.grid_columnconfigure(col, weight=1, uniform='historyfive')
        for col in range(4):
            if col < len(recent):
                who, card_name = recent[col]
                cell = tk.Frame(history_row, bg='#FFFFFF', bd=1, relief='groove')
                cell.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
                who_text = str(who).upper()
                if who_text == 'YOU':
                    who_text = 'YOU'
                elif who_text == 'OPENING':
                    who_text = 'OPEN'
                elif who_text.startswith('COMPUTER'):
                    who_text = who_text.replace('COMPUTER', 'CPU-').replace(' ', '')
                elif who_text.startswith('CPU') and '-' not in who_text:
                    who_text = who_text.replace('CPU ', 'CPU-')
                # Match the prominent player-header style used in the CPU/You score tiles.
                if who_text == 'YOU':
                    label_bg = '#17634E'
                    label_size = -19
                elif who_text == 'OPEN':
                    label_bg = '#A83240'
                    label_size = -18
                else:
                    label_bg = '#174A70'
                    label_size = -18
                tk.Label(cell, text=who_text, font=('Arial', label_size, 'bold'), bg=label_bg,
                         fg='#FFFFFF', padx=2, wraplength=90, pady=10, anchor='center').pack(fill='x')
                suit = card_name[-1] if card_name else '?'
                rank_text = card_name[:-1] if card_name else '?'
                card_w, card_h = 62, 94
                face = tk.Canvas(cell, width=card_w, height=card_h, bg='#FFFFFF',
                                 highlightthickness=0, bd=0)
                face.pack(pady=(1, 2))
                face.create_rectangle(4, 4, card_w-1, card_h-1, fill='#B66A75', outline='#B66A75')
                face.create_rectangle(1, 1, card_w-4, card_h-4, fill='#FFFEFF', outline='#8A6D80', width=1)
                ink = '#C52235' if suit in RED or suit == '★' else '#17221F'
                face.create_text(5, 4, text=rank_text, anchor='nw', font=('Arial', -17, 'bold'), fill=ink)
                face.create_text(card_w/2, card_h/2+3, text=suit, font=('Arial', -31, 'bold'), fill=ink)
                face.create_text(card_w-7, card_h-7, text=suit, anchor='se', font=('Arial', -14, 'bold'), fill=ink)
            else:
                empty = tk.Frame(history_row, bg='#FFFFFF', bd=1, relief='groove')
                empty.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
        # Waste bin occupies the fifth equal slot and is a real discard action.
        waste_cell = tk.Frame(history_row, bg='#FFFFFF', bd=1, relief='groove', cursor='hand2')
        waste_cell.grid(row=0, column=4, sticky='nsew', padx=1, pady=1)
        # Waste header uses the same bold, high-contrast player-label style and sizing.
        tk.Label(waste_cell, text='WASTE', font=('Arial', -18, 'bold'),
                 bg='#174A70', fg='#FFFFFF', padx=2, wraplength=90, pady=10,
                 anchor='center').pack(fill='x')
        icon_canvas = tk.Canvas(waste_cell, width=48, height=76, bg='#FFFFFF',
                                highlightthickness=0, bd=0, cursor='hand2')
        icon_canvas.pack(expand=True, pady=3, anchor='center')
        icon_canvas.create_rectangle(8, 22, 40, 67, outline='#A83240', width=3)
        icon_canvas.create_line(5, 18, 43, 18, fill='#A83240', width=4)
        icon_canvas.create_line(17, 13, 31, 13, fill='#A83240', width=3)
        icon_canvas.create_line(17, 29, 17, 59, fill='#A83240', width=2)
        icon_canvas.create_line(24, 29, 24, 59, fill='#A83240', width=2)
        icon_canvas.create_line(31, 29, 31, 59, fill='#A83240', width=2)
        for widget in (waste_cell, icon_canvas):
            widget.bind('<Button-1>', lambda event: self.discard_selected())
        # Joker placement mode: tapping a joker highlights every card that can
        # form a legal 3/4-card sequence or set with it. Tap a highlighted card
        # to choose that indicated meld and arrange the joker into it.
        # Keep the exact meld choices made by Sort Cards while the hand is
        # unchanged. Re-detecting on every refresh can choose a different
        # overlapping valid meld after card order changes, making colours look
        # as if groups jumped between rows even though the sort itself worked.
        hand_now = self.hands[0]
        current_signature = tuple(sorted(map(repr, hand_now)))
        cached_signature = getattr(self, '_sorted_group_cache_signature', None)
        cached_groups = getattr(self, '_sorted_group_cache', None)
        sorted_layout_active = cached_groups is not None and cached_signature == current_signature
        if sorted_layout_active:
            index_by_card = {card: idx for idx, card in enumerate(hand_now)}
            visual_groups = []
            for cached_kind, cached_cards in cached_groups:
                indices = tuple(sorted(index_by_card[c] for c in cached_cards if c in index_by_card))
                if len(indices) == len(cached_cards):
                    visual_groups.append((cached_kind, indices))
        else:
            self._sorted_group_cache = None
            self._sorted_group_cache_signature = None
            visual_groups = self.detect_hand_groups(hand_now)
        # Use fixed colours by meld type; the colour alone indicates the group.
        # Pure sequence = deep green; pure set = light green; impure sequence = blue;
        # impure set (a set using a joker) = yellow. Do not print SEQ/SET tags on cards.
        card_group = {}
        group_counts = {'pure': 0, 'impure': 0, 'set': 0}
        group_styles = {}
        for group_id, (kind, indices) in enumerate(visual_groups):
            group_counts[kind] += 1
            group_cards = [self.hands[0][idx] for idx in indices]
            has_joker = any(is_joker(card, self.wild_rank) for card in group_cards)
            if kind == 'pure':
                edge_colour, face_colour, text_colour = '#075D25', '#087A2D', '#FFFFFF'
            elif kind == 'impure':
                edge_colour, face_colour, text_colour = '#0759B5', '#C9E2FF', '#06458A'
            elif has_joker:
                edge_colour, face_colour, text_colour = '#A87800', '#FFF0A8', '#704D00'
            else:
                edge_colour, face_colour, text_colour = '#13803B', '#BDF5C9', '#075D25'
            group_styles[group_id] = (edge_colour, face_colour, text_colour, kind)
            for idx in indices:
                card_group[idx] = group_id
        # After Sort Cards, lay out each meld as an intact visual block. The
        # old fixed 3/3/3/final-row grid could split a 4-card group across rows,
        # making a correctly sorted meld look scattered. Keep the original
        # layout before sorting; use group-aware rows only while the cached sort
        # still matches the exact same physical hand.
        layout_rows = []
        if sorted_layout_active:
            group_at = {}
            grouped_indices = set()
            for _kind, indices in sorted(visual_groups, key=lambda item: min(item[1])):
                if indices:
                    start = min(indices)
                    if tuple(indices) == tuple(range(start, start + len(indices))):
                        group_at[start] = list(indices)
                        grouped_indices.update(indices)
            chunks = []
            i = 0
            while i < len(hand_now):
                if i in group_at:
                    chunk = group_at[i]
                    chunks.append(chunk)
                    i += len(chunk)
                else:
                    chunks.append([i])
                    i += 1
            current_row = []
            for chunk in chunks:
                if current_row and len(current_row) + len(chunk) > 4:
                    layout_rows.append(current_row)
                    current_row = []
                current_row.extend(chunk)
            if current_row:
                layout_rows.append(current_row)
        if not layout_rows:
            layout_rows = [list(range(0, min(3, len(hand_now)))),
                           list(range(3, min(6, len(hand_now)))),
                           list(range(6, min(9, len(hand_now))))]
            if len(hand_now) > 9:
                layout_rows.append(list(range(9, len(hand_now))))
            layout_rows = [items for items in layout_rows if items]
        card_position = {}
        for row_index, row_indices in enumerate(layout_rows):
            for col_index, card_index in enumerate(row_indices):
                card_position[card_index] = (row_index, col_index, len(row_indices))

        hand_title = f'YOUR HAND  •  {len(self.hands[0])} CARDS'
        if self.selected is not None:
            hand_title += f'   |   SELECTED: {ct(self.hands[0][self.selected])}'
        tk.Label(self.hand_area,text=hand_title,font=('Arial', -(20),'bold'),bg=PANEL,fg=GOLD).pack(pady=(4,2), ipady=2)
        # Removed the extra colour/group legend line as requested.
        row=tk.Frame(self.hand_area,bg=PANEL); row.pack(fill='both',expand=True,padx=3,pady=(3,2))
        hand=self.hands[0]; row_sizes=(3,3,3,max(0, len(hand)-9))
        # Draw each card as a miniature classic playing card, rather than a text button.
        # Four wider columns make card ranks/suits much easier to read; extra vertical space is used intentionally.
        screen_w = max(320, self.root.winfo_width() or self.root.winfo_screenwidth())
        screen_h = max(600, self.root.winfo_height() or self.root.winfo_screenheight())
        available_w = max(280, screen_w - 28)
        # Preserve the full left-to-right row width, while fitting all four rows
        # and the play controls underneath on a portrait screen.
        card_h_limit = max(60, min(142, (screen_h - 400) // max(4, len(layout_rows))))
        card_w_limit = int(card_h_limit / 1.38)
        card_w_3 = max(48, min(card_w_limit, (available_w - 18) // 3 - 4))
        card_w_4 = max(48, min(card_w_limit, (available_w - 24) // 4 - 4))
        card_w_5 = max(42, min(card_w_limit, (available_w - 30) // 5 - 4))
        for i,c in enumerate(hand):
            r,s=c[0],c[1]
            selected=(i==self.selected)
            card_row, card_col, cards_in_row = card_position.get(i, (0, i, 3))
            if cards_in_row >= 5:
                this_card_w = card_w_5
            elif cards_in_row == 4:
                this_card_w = card_w_4
            else:
                this_card_w = card_w_3
            this_card_h = min(int(this_card_w * 1.38), card_h_limit)

            canvas=tk.Canvas(row,width=this_card_w,height=this_card_h,
                             bg=PANEL,highlightthickness=0,bd=0,
                             cursor='hand2')
            canvas.card_index = i
            grid_span = max(1, 12 // cards_in_row)
            grid_col = card_col * grid_span
            canvas.grid(row=card_row, column=grid_col, columnspan=grid_span,
                        padx=2, pady=2, sticky='nsew')
            group_id = card_group.get(i)
            if group_id is not None:
                group_edge, group_face, group_text, kind = group_styles[group_id]
            else:
                group_edge, group_face, group_text, kind = '#C8AFC0', '#FFFEFF', '#3D3440', None
            joker_option = self.joker_place_index is not None and i in self.joker_place_options
            edge = '#D00045' if selected else ('#E6A000' if joker_option else group_edge)
            face = '#FFD24D' if selected else ('#FFF0A8' if joker_option else group_face)
            # Slight lower-right shadow and card face.
            canvas.create_rectangle(4,4,this_card_w-1,this_card_h-1,fill='#C79CB6',outline='#C79CB6')
            canvas.create_rectangle(1,1,this_card_w-4,this_card_h-4,fill=face,outline=edge,width=2 if selected else 1)
            fg = '#c52235' if s in RED or s=='★' else '#17221f'
            if r == 'JOKER':
                canvas.create_text(5,4,text='JOKER',anchor='nw',font=('Arial', -max(6, int(this_card_w*0.13)),'bold'),fill='#C02F59')
                canvas.create_text((this_card_w-3)/2,(this_card_h-4)/2,text='★',font=('Arial', -max(18, int(this_card_w*0.48)),'bold'),fill='#C02F59')
                canvas.create_text((this_card_w-3)/2,this_card_h-17,text='JOKER',font=('Arial', -max(6, int(this_card_w*0.12)),'bold'),fill='#C02F59')
            else:
                rank_text=rt(r)
                canvas.create_text(5,4,text=rank_text,anchor='nw',font=('Arial', -max(12, int(this_card_w*0.38)),'bold'),fill=fg)
                canvas.create_text((this_card_w-3)/2,(this_card_h-4)/2+2,text=s,font=('Arial', -max(18, int(this_card_w*0.60)),'bold'),fill=fg)
                # Replace the upside-down bottom-corner rank with a clear, upright suit symbol.
                canvas.create_text(this_card_w-8,this_card_h-8,text=s,anchor='se',font=('Arial', -max(10, int(this_card_w*0.24)),'bold'),fill=fg)
            if kind:
                # A clean coloured border is the only group indicator; no SEQ/SET text.
                canvas.create_rectangle(3,3,this_card_w-6,this_card_h-6,outline=group_edge,width=4)
            if joker_option:
                canvas.create_rectangle(2,2,this_card_w-5,this_card_h-5,outline='#E6A000',width=4)
                canvas.create_text(this_card_w/2,this_card_h-5,text='JOKER HERE',anchor='s',font=('Arial', -max(6, int(this_card_w*0.105)),'bold'),fill='#8A5200')
            if selected:
                canvas.create_rectangle(2,2,this_card_w-5,this_card_h-5,outline='#D00045',width=4)
                canvas.create_text(this_card_w/2,this_card_h-5,text='SELECTED',anchor='s',font=('Arial', -max(6, int(this_card_w*0.13)),'bold'),fill='#7B174F')
            canvas.bind('<Button-1>',lambda event,ix=i:self.select(ix))
        for c in range(12): row.grid_columnconfigure(c,weight=1,uniform='cardcols')
        for rr in range(len(layout_rows)):
            row.grid_rowconfigure(rr, weight=1, uniform='cardrows')
        # Two-column touch layout: seven tiny side-by-side buttons were too
        # cramped on a portrait phone. Larger targets are easier to tap.
        action_specs = [
            ('TAKE DISCARD', self.draw_discard, '#FFF2A8', '#7A183D'),
            (f'DRAW STOCK\n{len(self.stock)} CARDS', self.draw_stock, '#FFFFFF', DARK),
            ('SORT CARDS', self.sort_hand, '#D7E7FF', DARK),
            ('HINT', self.hint, '#8F315F', '#FFFFFF'),
            ('UNDO', self.undo, '#FFFFFF', DARK),
            ('DECLARE', self.declare, '#A9DED4', '#18352F'),
        ]
        # Two equal-height rows expand to fill the entire available action area.
        # Raised borders and bold embossed-style labels give the controls a tactile 3D look.
        self.actions.configure(bg='#DCE4EE', highlightbackground='#8B9BAE',
                               highlightthickness=2, bd=0)
        first_row = tk.Frame(self.actions, bg='#DCE4EE')
        first_row.grid(row=0, column=0, sticky='nsew', padx=3, pady=3)
        first_row.grid_rowconfigure(0, weight=1)
        for col, (label, command, colour, text_colour) in enumerate(action_specs[:3]):
            button = self.btn(first_row, label, command, bg=colour, fg=text_colour,
                              size=24, padx=2, pady=2, activebackground='#D98BAD')
            button.configure(relief='raised', bd=4, activeforeground=text_colour,
                             highlightthickness=1, highlightbackground='#FFFFFF',
                             font=('Arial', -24, 'bold'))
            button.grid(row=0, column=col, sticky='nsew', padx=3, pady=3)
            first_row.grid_columnconfigure(col, weight=1, uniform='top_actions')
        last_row=tk.Frame(self.actions,bg='#DCE4EE')
        last_row.grid(row=1,column=0,sticky='nsew',padx=3,pady=3)
        last_row.grid_rowconfigure(0, weight=1)
        for col, (label, command, colour, text_colour) in enumerate(action_specs[3:]):
            button = self.btn(last_row, label, command, bg=colour, fg=text_colour,
                              size=24, padx=2, pady=2, activebackground='#D98BAD')
            button.configure(relief='raised', bd=4, activeforeground=text_colour,
                             highlightthickness=1, highlightbackground='#FFFFFF',
                             font=('Arial', -24, 'bold'))
            button.grid(row=0,column=col,sticky='nsew',padx=3,pady=3)
            last_row.grid_columnconfigure(col,weight=1,uniform='bottom_actions')
        self.actions.grid_columnconfigure(0, weight=1)
        self.actions.grid_rowconfigure(0, weight=1, uniform='action_rows')
        self.actions.grid_rowconfigure(1, weight=1, uniform='action_rows')
        # Recover the human controls if a previous CPU callback left a stale
        # busy flag while it is already the human's turn. Never unlock controls
        # during a CPU turn or after the round has ended.
        if self.turn == 0 and not self.game_over and self.computer_after_id is None:
            self.busy = False

        self.status.config(text=self.last_message)
        for player_index, stat_label in getattr(self, 'player_stat_labels', {}).items():
            if player_index < len(self.hands):
                stat_label.config(text=f'{len(self.hands[player_index])} cards\\n{self.scores[player_index]} pts')
        can_draw = (self.turn == 0 and not self.has_drawn and not self.busy and not self.game_over)
        # Stock count is shown in the rebuilt DRAW STOCK action button.
        # Buttons are rebuilt on every refresh; explicitly set each state,
        # including the buttons nested inside the bottom action row.
        for parent in self.actions.winfo_children():
            children = parent.winfo_children() if isinstance(parent, tk.Frame) else [parent]
            for w in children:
                if isinstance(w, tk.Button):
                    if self.busy or self.game_over or self.turn != 0:
                        w.config(state='disabled')
                    elif w.cget('text').strip().upper().startswith('DISCARD SELECTED'):
                        w.config(state='normal' if self.has_drawn and self.selected is not None else 'disabled')
                    elif w.cget('text').strip().upper().startswith('DECLARE'):
                        w.config(state='normal' if not self.has_drawn and len(self.hands[0]) == 13 else 'disabled')
                    elif w.cget('text').strip().upper().startswith('UNDO'):
                        w.config(state='normal' if self.undo_state is not None else 'normal')
                    else:
                        w.config(state='normal')
    def detect_hand_groups(self, hand):
        """Choose disjoint, genuinely legal melds for truthful card highlighting."""
        n = len(hand)
        candidates = []
        for size in (3, 4):
            for inds in itertools.combinations(range(n), size):
                kind = group_kind([hand[j] for j in inds], self.wild_rank)
                if kind:
                    mask = sum(1 << j for j in inds)
                    # Pure sequence is the strongest useful meld; then impure
                    # sequence, then set. Coverage remains the primary objective.
                    priority = {'pure': 30, 'impure': 20, 'set': 10}[kind]
                    candidates.append((mask, kind, tuple(inds), priority))

        by_first = {i: [] for i in range(n)}
        for item in candidates:
            for i in item[2]:
                by_first[i].append(item)

        full = (1 << n) - 1
        memo = {}

        def solve(mask):
            if mask == full:
                return (0, 0, ())
            if mask in memo:
                return memo[mask]
            i = next(j for j in range(n) if not (mask >> j) & 1)

            # Option to leave this card ungrouped.
            best = solve(mask | (1 << i))
            for gm, kind, inds, priority in by_first[i]:
                if gm & mask:
                    continue
                covered, quality, groups = solve(mask | gm)
                candidate = (covered + len(inds),
                             quality + priority * len(inds),
                             groups + ((kind, inds),))
                if candidate[:2] > best[:2]:
                    best = candidate
            memo[mask] = best
            return best

        groups = list(solve(0)[2])
        # Stable visual ordering: pure/impure sequences first, then sets;
        # within each kind preserve the hand's order until Sort Cards is used.
        groups.sort(key=lambda g: ({'pure': 0, 'impure': 1, 'set': 2}[g[0]],
                                   min(g[1]), len(g[1])))
        return groups

    def _find_joker_placements(self, joker_index):
        """Return all legal 3/4-card melds that can use this joker."""
        hand=self.hands[0]
        joker=hand[joker_index]
        if not is_joker(joker,self.wild_rank):
            return {}
        options={}
        other=[i for i in range(len(hand)) if i != joker_index]
        for size in (2,3):
            for combo in itertools.combinations(other,size):
                cards=[joker]+[hand[j] for j in combo]
                kind=group_kind(cards,self.wild_rank)
                if kind:
                    inds=tuple(combo)
                    for idx in combo:
                        options.setdefault(idx,[]).append((kind,inds))
        return options

    def select(self,i):
        if self.busy or self.game_over: return
        self.play_sound('tap')
        hand=self.hands[0]
        # If a joker has already been tapped, tapping any yellow-highlighted
        # option chooses that exact valid meld; the hand is then neatly sorted.
        if self.joker_place_index is not None:
            choices=self.joker_place_options.get(i,[])
            if choices:
                # Prefer the most complete meld, then sequence over set.
                kind, inds=max(choices,key=lambda item:(len(item[1]), item[0] in ('pure','impure')))
                joker=hand[self.joker_place_index]
                group_cards=[hand[j] for j in inds]
                remaining=[c for j,c in enumerate(hand) if j != self.joker_place_index]
                insert_at=max((remaining.index(c) for c in group_cards),default=len(remaining)-1)+1
                remaining.insert(insert_at,joker)
                self.hands[0]=remaining
                self.joker_place_index=None; self.joker_place_options={}; self.selected=None
                self.sort_hand()
                self.last_message='Joker placed in the chosen '+('sequence.' if kind in ('pure','impure') else 'set.')
                self.status.config(text=self.last_message)
                return
            # Tapping the joker again cancels placement selection.
            if i==self.joker_place_index:
                self.joker_place_index=None; self.joker_place_options={}
                self.last_message='Joker placement cancelled.'
                self.refresh_hand(); self.status.config(text=self.last_message); return
        # Tapping any joker opens all available placement options. This is a
        # hand-arrangement helper and does not consume the player's turn.
        if is_joker(hand[i],self.wild_rank):
            options=self._find_joker_placements(i)
            if options:
                self.joker_place_index=i; self.joker_place_options=options; self.selected=None
                self.last_message=f'Joker has {len(options)} possible target card(s). Yellow cards show valid places; tap one.'
            else:
                self.joker_place_index=None; self.joker_place_options={}
                self.last_message='No valid sequence or set for this joker yet.'
            self.refresh_hand(); self.status.config(text=self.last_message); return
        if not self.has_drawn:
            self.last_message='Draw a card first. You can tap a joker to view its possible places.'
            self.status.config(text=self.last_message); return
        self.selected=i; self.refresh_hand()
    def draw_stock(self):
        # A normal turn starts with exactly 13 cards. Never silently draw into
        # an already-corrupted hand or allow a second draw in the same turn.
        if self.busy or self.has_drawn or self.game_over:
            return
        if len(self.hands[0]) != 13:
            self.last_message=f'Card-count check: your hand has {len(self.hands[0])} cards; expected 13. Start a new round to reset safely.'
            self.status.config(text=self.last_message)
            return
        if not self.stock:
            if len(self.discard) <= 1:
                self.finish_round(None, 'stock exhausted')
                return
            top=self.discard[-1]
            self.stock=self.discard[:-1]
            self.discard=[top]
            random.shuffle(self.stock)
        self.save_undo()
        card=self.stock.pop()
        self.hands[0].append(card)
        if len(self.hands[0]) != 14:
            # Roll back this operation rather than leave the turn half-updated.
            self.hands[0].pop()
            self.stock.append(card)
            self.last_message='Draw cancelled because the card count did not reach 14.'
            self.status.config(text=self.last_message)
            return
        self.has_drawn=True
        self.selected=None
        self.joker_place_index=None
        self.joker_place_options={}
        self.last_message='Card drawn. Select one card to discard.'
        self.refresh_hand()
    def draw_discard(self):
        if self.busy or self.has_drawn or self.game_over:
            return
        if len(self.hands[0]) != 13:
            self.last_message=f'Card-count check: your hand has {len(self.hands[0])} cards; expected 13. Start a new round to reset safely.'
            self.status.config(text=self.last_message)
            return
        if not self.discard:
            self.last_message='The discard pile is empty. Draw from STOCK instead.'
            self.status.config(text=self.last_message)
            return
        self.save_undo()
        card=self.discard.pop()
        self.hands[0].append(card)
        if len(self.hands[0]) != 14:
            self.hands[0].pop()
            self.discard.append(card)
            self.last_message='Taking the discard was cancelled because the card count did not reach 14.'
            self.status.config(text=self.last_message)
            return
        self.has_drawn=True
        self.selected=None
        self.joker_place_index=None
        self.joker_place_options={}
        self.last_message='Top discard taken. Select one card to discard.'
        self.refresh_hand()
    def discard_selected(self):
        if self.busy or not self.has_drawn: self.last_message='Draw a card first.'; self.status.config(text=self.last_message); return
        if len(self.hands[0]) != 14:
            self.last_message='Your hand should contain 14 cards before discarding.'; self.status.config(text=self.last_message); return
        if self.selected is None: self.last_message='Tap the card you want to discard.'; self.status.config(text=self.last_message); return
        self.save_undo(); card=self.hands[0].pop(self.selected); self.joker_place_index=None; self.joker_place_options={}; self.discard.append(card); self.discard_history.append(('YOU', ct(card))); self.selected=None; self.has_drawn=False; self.turn_no+=1
        if self.turn_no >= self.max_turns:
            self.finish_round(None, 'turn limit reached')
            return
        self.last_message=f'You discarded {ct(card)}. {self.names[1]} is thinking.'; self.turn=1; self.refresh_hand(); self.computer_after_id=self.root.after(1,self.computer_turn)
    def computer_turn(self):
        """Run every computer move in one fast callback; avoid slow UI waits."""
        self.computer_after_id=None
        if self.game_over:
            return
        self.busy=True
        self._computer_step()

    def _computer_step(self):
        """Play all CPUs quickly, then return control to the human.

        No repeated Tk after() delays and no full-screen redraw between CPU
        players. The decision routine is deliberately O(n^2) in every mode.
        """
        if self.game_over:
            self.busy=False
            return
        player_count=len(self.hands)
        safety=0
        while self.turn != 0 and not self.game_over and safety < player_count:
            safety += 1
            i=self.turn
            hand=self.hands[i]
            take_open=bool(self.discard and self.card_helps(self.discard[-1], hand)
                           and (self.difficulty != 'Easy' or random.random() < .55))
            if take_open:
                hand.append(self.discard.pop())
            else:
                if not self.stock and len(self.discard)>1:
                    top=self.discard[-1]
                    self.stock=self.discard[:-1]
                    random.shuffle(self.stock)
                    self.discard=[top]
                if self.stock:
                    hand.append(self.stock.pop())
                elif self.discard:
                    hand.append(self.discard.pop())
                else:
                    self.finish_round(None, 'stock exhausted')
                    return
            if len(hand)>13:
                idx=self.choose_discard(hand)
                thrown=hand.pop(idx)
                self.discard.append(thrown)
                self.discard_history.append((self.names[i].upper(), ct(thrown)))
            if len(hand)==13 and valid_declaration(hand,self.wild_rank):
                self.finish_round(i,'valid hand')
                return
            self.turn=(i+1) % player_count
        if not self.game_over:
            self.busy=False
            self.has_drawn=False
            self.selected=None
            self.last_message='Your turn: draw a card.'
            self.refresh_hand()

    def choose_discard(self,hand):
        """Fast discard scoring for every difficulty: O(n^2), never brute force."""
        n=len(hand)
        scores=[]
        for i,c in enumerate(hand):
            if is_joker(c,self.wild_rank):
                scores.append(1000.0)
                continue
            r,s=c[0],c[1]
            rv=14 if r==1 else r
            value=-points(c,self.wild_rank)*1.5
            connections=0
            for j,o in enumerate(hand):
                if i==j or is_joker(o,self.wild_rank):
                    continue
                ov=14 if o[0]==1 else o[0]
                if o[0]==r and o[1]!=s:
                    value+=5
                    connections+=1
                if o[1]==s:
                    gap=abs(rv-ov)
                    if gap==1:
                        value+=6
                        connections+=1
                    elif gap==2:
                        value+=2
                        connections+=1
            # Retain small skill differences without expensive meld enumeration.
            if self.difficulty=='Easy':
                value+=random.uniform(-2.5,2.5)
            elif self.difficulty=='Normal':
                value+=random.uniform(-0.8,0.8)
            else:  # Hard: more consistent decisions, still the same fast algorithm.
                value+=connections*0.15+random.uniform(-0.15,0.15)
            scores.append(value)
        lowest=min(scores)
        tolerance=2.5 if self.difficulty=='Easy' else (0.8 if self.difficulty=='Normal' else 0.15)
        return random.choice([i for i,v in enumerate(scores) if v<=lowest+tolerance])
    def sequence_potential(self,c,hand):
        if is_joker(c,self.wild_rank): return 100
        r,s=c[0],c[1]; total=0
        for o in hand:
            if o==c or is_joker(o,self.wild_rank): continue
            if o[1]==s and abs((14 if o[0]==1 else o[0])-(14 if r==1 else r))<=2: total+=2
            if o[0]==r and o[1]!=s: total+=1
        return total
    def card_helps(self,c,hand):
        """Prefer the open discard only when it forms a real connection."""
        if is_joker(c,self.wild_rank):
            return True
        rank, suit = c[0], c[1]
        value = 0
        for other in hand:
            if is_joker(other,self.wild_rank):
                # A joker can complete a run/set, but should not make every
                # unrelated open card automatically attractive.
                continue
            if other[0] == rank and other[1] != suit:
                value += 3
            if other[1] == suit:
                a = 14 if rank == 1 else rank
                b = 14 if other[0] == 1 else other[0]
                gap = abs(a-b)
                if gap == 1: value += 4
                elif gap == 2: value += 2
        # With no useful connection, keep drawing from the stock instead.
        return value >= 3
    def finish_round(self,winner,reason):
        """Save final hands and score the round exactly once, then show results."""
        if getattr(self, '_round_scored', False):
            self.show_round_result()
            return
        self.game_over=True; self.busy=False
        self.final_hands=copy.deepcopy(self.hands)
        self.final_wild_rank=self.wild_rank
        self.final_names=list(self.names)
        self.final_winner=winner
        self.final_reason=reason
        self.round_results=[]
        for i,h in enumerate(self.final_hands):
            pts=0 if winner is not None and i==winner else hand_score(h,self.wild_rank)
            self.scores[i]+=pts
            self.round_results.append((i,pts))
        self._round_scored=True
        self.show_round_result()

    def show_round_result(self):
        """Render the saved result without scoring a second time."""
        winner=self.final_winner
        reason=self.final_reason
        results=self.round_results
        self.clear()
        outer=tk.Frame(self.root,bg='#EEF2F7',bd=0,highlightthickness=0)
        outer.pack(fill='both',expand=True,padx=8,pady=8)
        f=tk.Frame(outer,bg='#EEF2F7',bd=0,highlightthickness=0)
        f.place(relx=0.5,rely=0.5,anchor='center',relwidth=1.0)
        try:
            self.root.update_idletasks()
            sw=max(300,min(900,int(self.root.winfo_width() if self.root.winfo_width()>100 else self.root.winfo_screenwidth())))
        except Exception:
            sw=max(300,min(900,int(self.root.winfo_screenwidth())))

        title_size=max(29,min(42,int(sw*.065)))
        headline_size=max(23,min(34,int(sw*.052)))
        body_size=max(17,min(24,int(sw*.038)))
        small_size=max(14,min(19,int(sw*.029)))
        wrap=max(250,int(sw*.92))

        titlebar=tk.Frame(f,bg='#073568',highlightthickness=2,highlightbackground='#D8B65A')
        titlebar.pack(fill='x',pady=(0,8))
        titlebar.grid_columnconfigure(1,weight=1)
        tk.Label(titlebar,text='♠',font=('Arial',-title_size,'bold'),bg='#073568',fg='#F4D77C').grid(row=0,column=0,padx=(8,2),pady=4)
        tk.Label(titlebar,text='ROUND COMPLETE',font=('Arial',-title_size,'bold'),bg='#073568',fg='#FFE8A0',anchor='center',justify='center',wraplength=wrap).grid(row=0,column=1,sticky='ew',pady=7)
        tk.Label(titlebar,text='♥',font=('Arial',-title_size,'bold'),bg='#073568',fg='#E64B5D').grid(row=0,column=2,padx=(2,8),pady=4)

        headline = f'{self.names[winner]} WINS!' if winner is not None else 'ROUND LIMIT REACHED'
        win_colour='#087A43' if winner == 0 else (GOLD if winner is not None else '#9B3B25')
        tk.Label(f,text=headline,font=('Arial',-headline_size,'bold'),bg='#EEF2F7',fg=win_colour,wraplength=wrap,justify='center').pack(fill='x',pady=(5,7))
        if winner is None:
            end_reason='The stock is exhausted.' if reason=='stock exhausted' else 'No valid declaration was made.'
            tk.Label(f,text=end_reason+' Penalty points are added for all players.',font=('Arial',-small_size,'bold'),bg='#EEF2F7',fg='#201820',wraplength=wrap,justify='center').pack(fill='x',pady=(0,6))

        section=tk.Frame(f,bg='#006B50',highlightthickness=1,highlightbackground='#B8D5CB')
        section.pack(fill='x',pady=(4,5))
        tk.Label(section,text='PENALTY POINTS FOR THIS ROUND',font=('Arial',-body_size,'bold'),bg='#006B50',fg='#FFFFFF',anchor='center',wraplength=wrap).pack(fill='x',padx=5,pady=7)

        for i,pts in results:
            is_winner=(winner is not None and i==winner)
            row_bg='#D8F0E5' if is_winner else '#FFFFFF'
            row_edge='#17634E' if is_winner else '#C6D0DC'
            row=tk.Frame(f,bg=row_bg,highlightthickness=2,highlightbackground=row_edge)
            row.pack(fill='x',pady=3)
            tk.Label(row,text=('🏆  ' if is_winner else '')+self.names[i],font=('Arial',-body_size,'bold'),bg=row_bg,fg='#103D30' if is_winner else '#201820',anchor='w',padx=10,pady=8,wraplength=int(sw*.63),justify='left').pack(side='left',fill='x',expand=True)
            tk.Label(row,text=f'{pts} pts',font=('Arial',-body_size,'bold'),bg=row_bg,fg='#087A43' if is_winner else GOLD,padx=10,pady=8).pack(side='right')

        tk.Label(f,text='TOTAL PENALTY POINTS  •  LOWER IS BETTER',font=('Arial',-small_size,'bold'),bg='#EEF2F7',fg='#3F3440',wraplength=wrap,justify='center').pack(fill='x',pady=(10,4))
        totals=tk.Frame(f,bg='#DCE6F0',highlightthickness=1,highlightbackground='#9FB2C7')
        totals.pack(fill='x',pady=(0,8))
        for i,n in enumerate(self.names):
            tk.Label(totals,text=f'{n}: {self.scores[i]}',font=('Arial',-small_size,'bold'),bg='#DCE6F0',fg='#102D52',padx=4,pady=4,wraplength=wrap).pack(fill='x')

        self.btn(f,'🃏   VIEW FINAL BOARDS',self.view_final_boards,bg='#7B174F',fg='#FFFFFF',size=body_size,pady=10,activebackground='#A12A6B').pack(fill='x',padx=2,pady=(4,5),ipady=5)
        self.btn(f,'▶   PLAY NEXT ROUND',self.start_game,bg='#00875F',fg='#FFFFFF',size=body_size,pady=9,activebackground='#00A778').pack(fill='x',padx=2,pady=(2,3),ipady=4)
        self.btn(f,'⌂   MAIN MENU',self.show_menu,bg='#06447D',fg='#FFFFFF',size=body_size,pady=8,activebackground='#0C5A9D').pack(fill='x',padx=2,pady=(1,2),ipady=3)
    def view_final_boards(self, player_index=0):
        """Show one player's final 13-card board at a time, with large readable cards."""
        if not self.final_hands:
            self.show_round_result()
            return
        player_index=max(0, min(int(player_index), len(self.final_hands)-1))
        self.final_view_index=player_index
        self.clear()
        bg='#EEF2F7'
        outer=tk.Frame(self.root,bg=bg,bd=0,highlightthickness=0)
        outer.pack(fill='both',expand=True,padx=5,pady=5)

        try:
            self.root.update_idletasks()
            sw=max(320, int(self.root.winfo_width()))
            sh=max(520, int(self.root.winfo_height()))
        except Exception:
            sw,sh=400,800
        title_size=max(18,min(28,int(sw*.058)))
        info_size=max(15,min(22,int(sw*.044)))
        small_size=max(11,min(15,int(sw*.030)))

        header=tk.Frame(outer,bg='#073568',highlightthickness=2,highlightbackground='#D8B65A')
        header.pack(fill='x',pady=(0,5))
        tk.Label(header,text='FINAL BOARD  •  ONE PLAYER',font=('Arial',-title_size,'bold'),bg='#073568',fg='#FFE8A0',pady=6).pack(fill='x')
        tk.Label(outer,text=f"WILD JOKER: {rt(self.final_wild_rank)}   •   ROUND {self.round_no}",font=('Arial',-small_size,'bold'),bg=bg,fg='#201820').pack(fill='x',pady=(0,4))

        # Player selector: one player's full hand is shown at once for large cards.
        nav=tk.Frame(outer,bg=bg)
        nav.pack(fill='x',pady=(0,5))
        prev_btn=self.btn(nav,'◀ PREVIOUS',lambda:self.view_final_boards((player_index-1)%len(self.final_hands)),bg='#06447D',fg='#FFFFFF',size=small_size,pady=7)
        prev_btn.pack(side='left',fill='x',expand=True,padx=(0,3))
        next_btn=self.btn(nav,'NEXT PLAYER ▶',lambda:self.view_final_boards((player_index+1)%len(self.final_hands)),bg='#06447D',fg='#FFFFFF',size=small_size,pady=7)
        next_btn.pack(side='left',fill='x',expand=True,padx=(3,0))
        if len(self.final_hands)<=1:
            prev_btn.config(state='disabled'); next_btn.config(state='disabled')

        hand=self.final_hands[player_index]
        pts=dict(self.round_results).get(player_index,0)
        winner=(self.final_winner is not None and player_index==self.final_winner)
        title_bg='#D8F0E5' if winner else '#DCE8F5'
        title_fg='#103D30' if winner else '#102D52'
        player_panel=tk.Frame(outer,bg='#FFFFFF',highlightthickness=2,highlightbackground='#17634E' if winner else '#AAB7C7')
        player_panel.pack(fill='x',pady=(0,5))
        tk.Label(player_panel,text=(('🏆  ' if winner else '')+self.final_names[player_index]),font=('Arial',-info_size,'bold'),bg=title_bg,fg=title_fg,pady=5).pack(fill='x')
        tk.Label(player_panel,text=f'{len(hand)} CARDS   •   {pts} PENALTY POINTS',font=('Arial',-small_size,'bold'),bg='#FFFFFF',fg='#201820',pady=4).pack(fill='x')

        groups=self.detect_hand_groups(hand)
        group_by_index={}
        group_desc=[]
        palette=[('#087A2D','#BDF5C9','#075D25'),('#0759B5','#C9E2FF','#06458A'),('#A64B00','#FFE0B2','#7A3500'),('#7B2CBF','#E9D5FF','#5A189A'),('#B51F48','#FFD6E0','#8D1637'),('#087E8B','#C9F4F4','#075E66'),('#8A6D00','#FFF3A6','#655000'),('#4F5D75','#DDE3EE','#354052')]
        for gid,(kind,indices) in enumerate(groups):
            edge,face,text_colour=palette[gid%len(palette)]
            label=('PURE SEQ' if kind=='pure' else 'IMPURE SEQ' if kind=='impure' else 'SET')+f' {gid+1}'
            group_desc.append(label)
            for idx in indices:
                group_by_index[idx]=(edge,face,text_colour,label)

        # Large card faces, laid out in rows similar to the live hand board.
        board=tk.Frame(outer,bg='#FFFFFF',highlightthickness=1,highlightbackground='#AAB7C7')
        # Keep the cards at their requested size instead of letting the empty
        # board expand across the whole phone screen and push navigation away.
        board.pack(fill='x',expand=False,padx=1,pady=2)
        card_w=max(66,min(108,(sw-28)//4))
        card_h=int(card_w*1.48)
        cols=4
        for idx,card in enumerate(hand):
            row=idx//cols; col=idx%cols
            style=group_by_index.get(idx)
            edge,face,text_colour,label=style if style else ('#B9AAB5','#FFFEFF','#332833','UNMATCHED')
            cell=tk.Frame(board,bg=face,highlightthickness=3,highlightbackground=edge)
            cell.grid(row=row,column=col,sticky='nsew',padx=3,pady=4)
            face_canvas=tk.Canvas(cell,width=card_w,height=card_h,bg=face,highlightthickness=0,bd=0)
            face_canvas.pack(padx=1,pady=(1,0))
            face_canvas.create_rectangle(2,2,card_w-3,card_h-3,fill=face,outline=edge,width=2)
            # Cards are stored as (rank, suit, physical_deck_id); only the
            # first two fields are display data. Unpacking the whole tuple
            # raised ValueError and left the final board blank.
            rank,suit=card[0],card[1]
            ink='#C52235' if suit in RED or suit=='★' else '#17221F'
            if rank=='JOKER':
                face_canvas.create_text(5,4,text='JOKER',anchor='nw',font=('Arial',-max(9,int(card_w*.14)),'bold'),fill='#C02F59')
                face_canvas.create_text(card_w/2,card_h*.49,text='★',font=('Arial',-max(30,int(card_w*.52)),'bold'),fill='#C02F59')
                face_canvas.create_text(card_w/2,card_h-8,text='JOKER',anchor='s',font=('Arial',-max(9,int(card_w*.13)),'bold'),fill='#C02F59')
            else:
                face_canvas.create_text(6,4,text=rt(rank),anchor='nw',font=('Arial',-max(18,int(card_w*.29)),'bold'),fill=ink)
                face_canvas.create_text(card_w/2,card_h*.53,text=suit,font=('Arial',-max(34,int(card_w*.56)),'bold'),fill=ink)
                face_canvas.create_text(card_w-7,card_h-7,text=suit,anchor='se',font=('Arial',-max(14,int(card_w*.20)),'bold'),fill=ink)
            # Keep the text printed under each card at its original readable size.
            # The enlarged font is reserved for the summary lines BELOW the board.
            tk.Label(cell,text=label,font=('Arial',-max(8,int(sw*.022)),'bold'),bg=face,fg=text_colour,wraplength=card_w-4,justify='center').pack(fill='x',padx=1,pady=(0,3))
            board.grid_columnconfigure(col,weight=1,uniform='finalcards')
        for row_index in range((len(hand)+cols-1)//cols):
            board.grid_rowconfigure(row_index, weight=0)
        if group_desc:
            tk.Label(outer,text='GROUPS: '+', '.join(group_desc),font=('Arial',-max(17,min(22,int(sw*.032))),'bold'),bg=bg,fg='#3F3440',wraplength=sw-16,justify='center').pack(fill='x',pady=(12,8))
        else:
            tk.Label(outer,text='NO VALID GROUPS DETECTED',font=('Arial',-max(18,min(24,int(sw*.036))),'bold'),bg=bg,fg='#9B3B25',wraplength=max(280,sw-12),justify='center').pack(fill='x',pady=(6,4),padx=2)

        # Show the player's remaining unmatched cards' penalty explicitly.
        unmatched=[idx for idx in range(len(hand)) if idx not in group_by_index]
        unmatched_points=sum(points(hand[idx],self.final_wild_rank) for idx in unmatched)
        tk.Label(outer,text=f'UNMATCHED CARDS: {len(unmatched)}   •   THEIR POINTS: {unmatched_points}',font=('Arial',-max(18,min(24,int(sw*.036))),'bold'),bg=bg,fg='#9B3B25' if unmatched else '#087A43',wraplength=max(280,sw-12),justify='center').pack(fill='x',pady=(5,4),padx=2)
        unmatched_names=', '.join(ct(hand[idx]) for idx in unmatched) if unmatched else 'None — all cards are grouped'
        tk.Label(outer,text='Penalty cards: '+unmatched_names,font=('Arial',-max(17,min(23,int(sw*.034))),'bold'),bg=bg,fg='#9B3B25' if unmatched else '#087A43',wraplength=max(280,sw-12),justify='center').pack(fill='x',pady=(4,10),padx=2)

        bottom=tk.Frame(outer,bg=bg)
        # Only the three bottom navigation buttons expand to use the remaining height.
        bottom.pack(fill='both',expand=True,pady=(3,0))
        nav_font_size=max(17,min(25,int(sw*.046)))
        self.btn(bottom,'⬅  BACK TO RESULT',self.show_round_result,bg='#06447D',fg='#FFFFFF',size=nav_font_size,pady=7).pack(fill='both',expand=True,pady=2)
        self.btn(bottom,'▶  PLAY NEXT ROUND',self.start_game,bg='#00875F',fg='#FFFFFF',size=nav_font_size,pady=7).pack(fill='both',expand=True,pady=2)
        self.btn(bottom,'⌂  MAIN MENU',self.show_menu,bg='#7B174F',fg='#FFFFFF',size=nav_font_size,pady=7).pack(fill='both',expand=True,pady=2)

    def declare(self):
        if self.busy: return
        if self.has_drawn: self.last_message='Discard one card before declaring.'; self.status.config(text=self.last_message); return
        if len(self.hands[0]) != 13:
            self.last_message='You must have exactly 13 cards to declare.'; self.status.config(text=self.last_message); return
        if valid_declaration(self.hands[0],self.wild_rank): self.finish_round(0,'valid hand')
        else: self.show_big_popup('Invalid Declaration','A valid declaration needs all 13 cards grouped, at least two sequences, and at least one pure sequence.', confirm_text='OK')
    def sort_hand(self):
        """Arrange legal melds as clear, contiguous blocks, then sort loose cards."""
        self.play_sound('sort')
        hand = list(self.hands[0])
        if not hand:
            return
        original_signature = sorted(map(repr, hand))
        # Clear any old sort layout before calculating groups for this exact hand.
        self._sorted_group_cache = None
        self._sorted_group_cache_signature = None
        groups = self.detect_hand_groups(hand)
        used = set()
        ordered = []
        cached_groups = []

        def rank_value(card):
            return 14 if card[0] == 1 else (0 if card[0] == 'JOKER' else card[0])

        def sequence_order(cards, kind):
            """Order a legal run in rank order, placing jokers in missing slots."""
            fixed = [c for c in cards if not is_joker(c, self.wild_rank)]
            wilds = [c for c in cards if is_joker(c, self.wild_rank)]
            if not fixed:
                return sorted(cards, key=lambda c: (rank_value(c), SUIT_ORDER.get(c[1], 99), c[2]))

            raw = [c[0] for c in fixed]
            variants = []
            high = [14 if r == 1 else r for r in raw]
            variants.append(high)
            if 1 in raw:
                variants.append([1 if r == 1 else r for r in raw])

            chosen = None
            for vals in variants:
                for run_start in range(1, 15 - len(cards) + 1):
                    run = list(range(run_start, run_start + len(cards)))
                    if not all(v in run for v in vals):
                        continue
                    missing = [v for v in run if v not in set(vals)]
                    if len(missing) != len(wilds):
                        continue
                    by_rank = {}
                    for card in fixed:
                        value = 14 if card[0] == 1 else card[0]
                        by_rank[value] = card
                    pool = iter(wilds)
                    candidate = []
                    for value in run:
                        candidate.append(by_rank[value] if value in by_rank else next(pool))
                    chosen = candidate
                    break
                if chosen is not None:
                    break
            return chosen or sorted(cards, key=lambda c: (rank_value(c), SUIT_ORDER.get(c[1], 99), c[2]))

        def group_sort_key(group):
            kind, inds = group
            cards = [hand[i] for i in inds]
            order = {'pure': 0, 'impure': 1, 'set': 2}.get(kind, 3)
            if kind in ('pure', 'impure'):
                sorted_cards = sequence_order(cards, kind)
                return (order, SUIT_ORDER.get(sorted_cards[0][1], 99), rank_value(sorted_cards[0]), len(cards))
            natural_ranks = [c[0] for c in cards if not is_joker(c, self.wild_rank)]
            group_rank = natural_ranks[0] if natural_ranks else 99
            return (order, rank_value((group_rank, '♠', 0)) if isinstance(group_rank, int) else 99,
                    min(SUIT_ORDER.get(c[1], 99) for c in cards), len(cards))

        # Stable, predictable presentation: pure runs, impure runs, sets, then
        # loose cards. This avoids the old behaviour where group order depended
        # on whichever card happened to appear first in the unsorted hand.
        groups = sorted(groups, key=group_sort_key)
        for kind, inds in groups:
            group_cards = [hand[i] for i in inds]
            if kind in ('pure', 'impure'):
                group_cards = sequence_order(group_cards, kind)
            else:
                group_cards = sorted(group_cards, key=lambda c: (
                    c[0] == 'JOKER', c[0] == self.wild_rank,
                    SUIT_ORDER.get(c[1], 99), rank_value(c), c[2]))
            ordered.extend(group_cards)
            used.update(inds)
            cached_groups.append((kind, tuple(group_cards)))

        leftovers = [c for i, c in enumerate(hand) if i not in used]
        leftovers.sort(key=lambda c: (
            is_joker(c, self.wild_rank), SUIT_ORDER.get(c[1], 99),
            rank_value(c), c[2]))
        ordered.extend(leftovers)

        # Sorting is display-only: never lose, duplicate, or create a card.
        if len(ordered) != len(hand) or sorted(map(repr, ordered)) != original_signature:
            self.last_message = 'Sort cancelled: safety check kept your original cards.'
            ordered = hand[:]
            self._sorted_group_cache = None
            self._sorted_group_cache_signature = None
        else:
            self.last_message = 'Cards sorted: each valid group is together and runs are in rank order.'
            self._sorted_group_cache = cached_groups
            self._sorted_group_cache_signature = tuple(sorted(map(repr, ordered)))

        self.hands[0] = ordered
        self.selected = None
        self.joker_place_index = None
        self.joker_place_options = {}
        self.refresh_hand()

    def hint(self):
        groups=[]
        hand=self.hands[0]
        for size in (3,4):
            for inds in itertools.combinations(range(len(hand)),size):
                g=[hand[i] for i in inds]; k=group_kind(g,self.wild_rank)
                if k: groups.append((k,g))
        if groups:
            kind,g=max(groups,key=lambda x:(x[0]=='pure',len(x[1])))
            self.last_message='Hint: '+kind.upper()+' — '+' '.join(ct(c) for c in g)
        else: self.last_message='Hint: look for same-suit runs or same-rank sets.'
        self.status.config(text=self.last_message)
    def save_undo(self):
        self.undo_state=(copy.deepcopy(self.hands),copy.deepcopy(self.stock),copy.deepcopy(self.discard),self.turn,self.has_drawn,self.selected,self.turn_no,self.last_message,copy.deepcopy(self.discard_history))
    def undo(self):
        if not self.undo_state or self.busy:
            self.last_message='Undo is available after your last draw or discard.'; self.status.config(text=self.last_message); return
        # If the human just discarded, cancel the scheduled computer turn
        # before restoring the saved state. Otherwise a stale callback could
        # make a computer play after the human has undone the action.
        if self.computer_after_id is not None:
            try: self.root.after_cancel(self.computer_after_id)
            except Exception: pass
            self.computer_after_id=None
        self.hands,self.stock,self.discard,self.turn,self.has_drawn,self.selected,self.turn_no,self.last_message,self.discard_history=copy.deepcopy(self.undo_state)
        self.undo_state=None; self.busy=False; self.game_over=False; self.refresh_hand()
    def show_big_popup(self, heading, message, confirm_text='OK', cancel_text=None, on_confirm=None):
        # Large custom popup: more readable than platform-native tiny message boxes.
        win=tk.Toplevel(self.root)
        win.title(heading)
        win.configure(bg='#F7EDF3')
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        width=max(300,min(560,self.root.winfo_width()-24 if self.root.winfo_width()>100 else 420))
        win.geometry(f'{width}x260')
        win.resizable(False,False)
        tk.Label(win,text=heading,font=('Arial',-22,'bold'),bg='#642052',fg='#FFFFFF',pady=13,wraplength=width-24).pack(fill='x')
        tk.Label(win,text=message,font=('Arial',-17,'bold'),bg='#F7EDF3',fg='#24131F',wraplength=width-36,justify='center',padx=12,pady=20).pack(fill='both',expand=True)
        buttons=tk.Frame(win,bg='#F7EDF3'); buttons.pack(fill='x',padx=10,pady=(0,12))
        def finish(accepted):
            try: win.grab_release()
            except Exception: pass
            win.destroy()
            if accepted and on_confirm: on_confirm()
        if cancel_text:
            tk.Button(buttons,text=cancel_text,command=lambda:finish(False),font=('Arial',-16,'bold'),bg='#D9E2EA',fg='#201820',height=2).pack(side='left',expand=True,fill='x',padx=4)
        tk.Button(buttons,text=confirm_text,command=lambda:finish(True),font=('Arial',-16,'bold'),bg='#642052',fg='#FFFFFF',height=2).pack(side='left' if cancel_text else 'top',expand=True,fill='x',padx=4)
        win.bind('<Escape>',lambda e:finish(False))
        win.bind('<Return>',lambda e:finish(True))
        win.update_idletasks()
        x=max(0,(win.winfo_screenwidth()-width)//2); y=max(0,(win.winfo_screenheight()-win.winfo_height())//2)
        win.geometry(f'+{x}+{y}')
        win.focus_force()

    def confirm_menu(self):
        self.show_big_popup('Return to Menu','Leave this round and return to the main menu?',confirm_text='YES, MENU',cancel_text='CANCEL',on_confirm=self.show_menu)

if __name__ == '__main__':
    # Diagnostic launcher: capture the real startup exception instead of
    # silently closing when Tkinter raises an error.
    import traceback
    import os

    root = None
    try:
        root = tk.Tk()
        app = RummyApp(root)
        root.mainloop()
    except Exception:
        error_text = traceback.format_exc()
        # Try common writable locations; keep the full traceback for diagnosis.
        saved_path = None
        for folder in (os.getcwd(), os.path.dirname(os.path.abspath(__file__))):
            try:
                path = os.path.join(folder, 'rummy_error.txt')
                with open(path, 'w', encoding='utf-8') as error_file:
                    error_file.write(error_text)
                saved_path = path
                break
            except Exception:
                pass
        try:
            if root is None:
                root = tk.Tk()
            messagebox.showerror(
                'Rummy startup error',
                error_text[-3500:] + (f"\n\nFull error saved to:\n{saved_path}" if saved_path else '')
            )
            root.mainloop()
        except Exception:
            print(error_text)

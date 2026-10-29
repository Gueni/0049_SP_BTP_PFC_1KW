#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?                _                   __
#?          _____(_)___ _____  ____ _/ /____
#?         / ___/ / __ `/ __ \/ __ `/ / ___/
#?        (__  ) / /_/ / / / / /_/ / (__  )
#?       /____/_/\__, /_/ /_/\__,_/_/____/
#?              /____/
#?
#?
#? Name:        signals.py
#? Purpose:     names (and units) of the columns of a PLECS To File CSV, read from the model, not written by hand.
#?              Standalone (standard library only): copy the file to any project.
#?                  names = SignalNames.read('result.csv', 'model.plecs')
#?
#? Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
#?
#? Created:     10/29/2026
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
#? -------------------------------------------------------------------------------
import math
import re
from   pathlib              import  Path
#?----------------------------------------------------------------------------------------------------------------------------------------
class SignalNames:
    """Column names of a To File CSV.

    1. Header: with 'Write signal names' on, PLECS writes 'component:probe signal' per scalar and
       'component:probe signal:k' per element of a vector.
    2. Vector elements are named after the entries of the mask probe of the probed block (library reference or
       masked subsystem, active configuration).
    3. Columns PLECS cannot name ('ToFile_In_1', '<undefined>', e.g. signals routed through nested subsystems) are
       named by tracing the To File input back through Mux, subsystem ports, Goto/From and hold blocks to the probes.
    Elements that stay unresolved keep their index, or take their names from labels {'component:probe signal': [names]}.
    Units are guessed from the probe and signal names (UNIT_KEYWORDS: keyword -> unit, first match wins)."""

    UNIT_KEYWORDS                   = {
                                        'gate'          : '[ / ]',
                                        'temperature'   : '[ °C ]',
                                        'temp'          : '[ °C ]',
                                        'voltage'       : '[ V ]',
                                        'current'       : '[ A ]',
                                        'loss'          : '[ W ]',
                                        'power'         : '[ W ]',
                                      }
    GENERIC                         = re.compile(r'^(<undefined>|ToFile_In_\d+|In\d*|Signal\d*|)$', re.I)   # names PLECS gives unnamed signals
    PASS_THROUGH                    = {'ZeroOrderHold', 'Memory', 'Delay', 'DataTypeConversion', 'SignalSwitch'}   # input 1 -> output, same names

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? One-line entry point
    #?------------------------------------------------------------------------------------------------------------------------------------
    @classmethod
    def read(cls, csv_file, model_path, lib_dir=None, modelvars=None, labels=None, units=False, tofile=None, unit_keywords=None):
        """Names of the columns of csv_file after the time column, in order; (names, units) with units=True.
        lib_dir  : folder of the PLECS libraries the model references (default: the model's folder)
        modelvars: ModelVars dict, to resolve configurations given as expressions ('PFC.Config')
        labels   : {'component:probe signal': [element names]} for vectors that cannot be resolved
        tofile   : name of the To File block when the model has several"""
        sn                          = cls(model_path, lib_dir, modelvars, labels)
        names, hints                = sn.columns(csv_file, tofile)
        if not units:
            return names
        keywords                    = unit_keywords or cls.UNIT_KEYWORDS
        return names, [next((u for kw, u in keywords.items() if kw in h), '[ / ]') for h in hints]

    @classmethod
    def units_from_names(cls, names, unit_keywords=None):
        """Unit of each name guessed from its keywords ('[ / ]' if none matches)."""
        keywords                    = unit_keywords or cls.UNIT_KEYWORDS
        return [next((u for kw, u in keywords.items() if kw in n.lower()), '[ / ]') for n in names]

    def __init__(self, model_path, lib_dir=None, modelvars=None, labels=None):
        self.root                   = self.parse(model_path)
        self.lib_dir                = Path(lib_dir) if lib_dir else Path(model_path).parent
        self.modelvars              = modelvars or {}
        self.labels                 = labels or {}
        self._libs                  = {}

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? .plecs file: tree of 'Tag { key value ... }' blocks
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def parse(path):
        """{'tag', 'props' [(key, value) in order], 'children'} of a .plecs file."""
        root                        = {'tag': None, 'props': [], 'children': []}
        stack                       = [root]
        with open(path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                s                   = line.strip()
                if s.endswith('{') and s[:-1].strip().isidentifier():
                    node            = {'tag': s[:-1].strip(), 'props': [], 'children': []}
                    stack[-1]['children'].append(node)
                    stack.append(node)
                elif s == '}' and len(stack) > 1:
                    stack.pop()
                elif s.startswith('"') and stack[-1]['props']:                  # continuation of a string split over lines
                    key, value      = stack[-1]['props'][-1]
                    stack[-1]['props'][-1] = (key, value + (s[1:-1] if s.endswith('"') else s[1:]))
                elif s:
                    key, _, value   = s.partition(' ')
                    stack[-1]['props'].append((key, value.strip().strip('"')))
        return root

    @staticmethod
    def prop(node, key):
        return next((v for k, v in node['props'] if k == key), None) if node else None

    @staticmethod
    def kids(node, tag):
        return [c for c in node['children'] if c['tag'] == tag] if node else []

    @staticmethod
    def param(comp, variable):
        return next((SignalNames.prop(p, 'Value') for p in SignalNames.kids(comp, 'Parameter')
                     if SignalNames.prop(p, 'Variable') == variable), None)

    @staticmethod
    def component(schematic, name):
        return next((c for c in SignalNames.kids(schematic, 'Component') if SignalNames.prop(c, 'Name') == name), None)

    @staticmethod
    def find(node, name):
        """First Component named name anywhere below node."""
        for child in node['children']:
            if child['tag'] == 'Component' and SignalNames.prop(child, 'Name') == name:
                return child
            found                   = SignalNames.find(child, name)
            if found:
                return found
        return None

    def _top(self):
        """Top-level schematic of the model."""
        plecs                       = next((c for c in self.root['children'] if c['tag'] == 'Plecs'), self.root)
        return next(iter(self.kids(plecs, 'Schematic')), plecs)

    def _library_block(self, comp):
        """Library block a Reference component points to ('Power/EVSE\\/GRID' -> Power.plecs, block 'EVSE/GRID')."""
        src                         = self.prop(comp, 'SrcComponent')
        parts                       = re.split(r'(?<!\\)/', src.replace('\\\\', '\\'), maxsplit=1) if src else []
        if len(parts) != 2:
            return None
        lib_file                    = self.lib_dir / f"{parts[0]}.plecs"
        if not lib_file.exists():
            return None
        if lib_file not in self._libs:
            self._libs[lib_file]    = self.parse(lib_file)
        return self.find(self._libs[lib_file], parts[1].replace('\\/', '/'))

    def _block(self, comp):
        """Component holding the content of comp: the library block of a Reference, else comp itself."""
        return self._library_block(comp) if self.prop(comp, 'Type') == 'Reference' else comp

    def _resolve(self, expr):
        """Value of a configuration expression: a number or a dotted ModelVars path ('PFC.Config')."""
        if expr is None:
            return None
        if expr.strip().isdigit():
            return int(expr)
        d                           = self.modelvars
        try:
            for k in expr.strip().split('.'):
                d                   = d[k]
            return int(d)
        except (KeyError, TypeError, ValueError):
            return None

    def _schematics(self, comp, config_name=None):
        """[(configuration name, schematic)] of comp: the active configuration first (or the named one), then the others."""
        blk                         = self._block(comp)
        configs                     = next(iter(self.kids(blk, 'Configurations')), None)
        if configs is None:
            return [(None, s) for s in self.kids(blk, 'Schematic')]
        names                       = [v for k, v in configs['props'] if k == 'Name']
        pairs                       = list(zip(names, self.kids(configs, 'Schematic')))
        if config_name is not None:
            return [p for p in pairs if p[0] == config_name]
        idx                         = self._resolve(self.param(comp, 'Configuration'))
        if idx and 1 <= idx <= len(pairs):
            pairs.insert(0, pairs.pop(idx - 1))
        return pairs

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Mask probes: element names of a probed vector signal
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def _width(schematic, name):
        """Signal width of a placeholder Constant (zeros(a,b) -> a*b); 1 otherwise."""
        c                           = SignalNames.find(schematic, name) if schematic else None
        value                       = SignalNames.param(c, 'Value') if c and SignalNames.prop(c, 'Type') == 'Constant' else None
        dims                        = [int(x) for x in re.findall(r'\d+', value)] if value and value.startswith(('zeros', 'ones')) else []
        return math.prod(dims) if dims else 1

    def _mask_entries(self, comp, probe):
        """[(element label, underlying signal)] of the mask probe `probe` of comp (active configuration); None if unknown."""
        blk                         = self._block(comp) if comp else None
        mp                          = next((c for c in self.kids(blk, 'MaskProbe') if self.prop(c, 'Name') == probe), None)
        if mp is None:
            return None
        active, schematic           = None, blk
        if self.kids(blk, 'Configurations'):
            idx                     = self._resolve(self.param(comp, 'Configuration'))
            configs                 = self.kids(blk, 'Configurations')[0]
            names                   = [v for k, v in configs['props'] if k == 'Name']
            if idx is None or not 1 <= idx <= len(names):
                return None
            active, schematic       = names[idx - 1], self.kids(configs, 'Schematic')[idx - 1]
        out                         = []
        for p in self.kids(mp, 'Probe'):
            if active is not None and self.prop(p, 'Path') not in (None, '', active):
                continue
            entry                   = self.prop(p, 'Component')
            signals                 = re.findall(r'"([^"]*)"', self.prop(p, 'Signals') or '')
            w                       = self._width(schematic, entry)
            for s in signals:
                label               = entry if len(signals) == 1 else s if entry.lower() in probe.lower() else f"{entry} {s}"
                out                += [(label if w == 1 else f"{label} {k}", s) for k in range(1, w + 1)]
        return out

    def _by_path(self, path, name):
        """Component `name` at Path 'A/Config/B' (relative to the top level; configuration names select a schematic)."""
        sch                         = self._top()
        parts                       = [p for p in re.split(r'(?<!\\)/', path or '') if p]
        i                           = 0
        while i < len(parts):
            comp                    = self.component(sch, parts[i])
            if comp is None:
                return self.find(self._top(), name)                             # unexpected path: first match anywhere
            pairs                   = self._schematics(comp, parts[i + 1]) if i + 1 < len(parts) else []
            if pairs:
                i                  += 1                                         # next part was a configuration name
            pairs                   = pairs or self._schematics(comp)
            if not pairs:
                return self.find(self._top(), name)
            sch                     = pairs[0][1]
            i                      += 1
        return self.component(sch, name) or self.find(self._top(), name)

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Tracing a signal back to its probes: entries (component, probe signal, element label, hint), one per scalar
    #?------------------------------------------------------------------------------------------------------------------------------------
    def _source(self, schematic, name, terminal):
        """(component, terminal) driving input `terminal` of component `name` in schematic."""
        def hit(node):
            if self.prop(node, 'DstComponent') == name and self.prop(node, 'DstTerminal') == str(terminal):
                return True
            return any(hit(b) for b in self.kids(node, 'Branch'))
        for c in self.kids(schematic, 'Connection'):
            if hit(c):
                return self.prop(c, 'SrcComponent'), int(self.prop(c, 'SrcTerminal') or 1)
        return None

    def _walk(self, schematic, ctx):
        """(ctx, component) for every component below schematic (every configuration)."""
        for c in self.kids(schematic, 'Component'):
            yield ctx, c
            for _, s in self._schematics(c) if self.prop(c, 'Type') != 'Reference' else []:
                yield from self._walk(s, ctx + [(s, c)])

    def _trace_input(self, ctx, name, terminal, depth):
        src                         = self._source(ctx[-1][0], name, terminal)
        return self._trace(ctx, *src, depth + 1) if src else None

    def _trace(self, ctx, name, terminal, depth=0):
        """Entries of output `terminal` of component `name` in ctx[-1] (ctx: [(schematic, owner component)] from the top)."""
        sch, owner                  = ctx[-1]
        comp                        = self.component(sch, name)
        if comp is None or depth > 200:
            return None
        typ                         = self.prop(comp, 'Type')
        if typ == 'PlecsProbe':
            out                     = []
            for p in self.kids(comp, 'Probe'):
                target, path        = self.prop(p, 'Component'), self.prop(p, 'Path')
                tcomp               = self._by_path(path, target)
                order               = [self.prop(m, 'Name') for m in self.kids(self._block(tcomp), 'MaskProbe')] if tcomp else []
                signals             = re.findall(r'"([^"]*)"', self.prop(p, 'Signals') or '')
                for s in sorted(signals, key=lambda s: order.index(s) if s in order else len(order)):   # PLECS: mask probe order
                    entries         = self.labels.get(f"{target}:{s}")
                    entries         = [(l, '') for l in entries] if entries else self._mask_entries(tcomp, s)
                    if entries and len(entries) == 1:
                        entries     = [('', entries[0][1])]                     # scalar: no element label
                    out            += [(target, s, l, h) for l, h in entries] if entries else [(target, s, '', '')]
            return out
        if typ == 'SignalMux':
            width                   = self.param(comp, 'Width') or '1'
            nums                    = [int(float(x)) for x in re.findall(r'-?\d+(?:\.\d+)?', width)]
            widths                  = nums if width.strip().startswith('[') else [1] * (nums[0] if nums else 1)
            out                     = []
            for k, w in enumerate(widths):
                sub                 = self._trace_input(ctx, name, k + 2, depth) or []
                if w > 0 and len(sub) != w:
                    base            = sub[0] if len(sub) == 1 else (name, f"In{k + 1}", '', '')
                    sub             = [(base[0], base[1], f"{base[2]} {j}".strip(), base[3]) for j in range(1, w + 1)]
                out                += sub
            return out
        if typ == 'Input' and owner is not None:                                # subsystem port: continue outside
            n                       = self._terminal_number(owner, 'Input', self.param(comp, 'Index'))
            return self._trace_input(ctx[:-1], self.prop(owner, 'Name'), n, depth) if n else None
        if typ in ('Subsystem', 'ConfigurableSubsystem') or (typ == 'Reference' and self._block(comp)):
            terms                   = self._block(comp) and self.kids(self._block(comp), 'Terminal') or self.kids(comp, 'Terminal')
            t                       = terms[terminal - 1] if 0 < terminal <= len(terms) else None
            idx                     = self.prop(t, 'Index') if t and self.prop(t, 'Type') == 'Output' else None
            for _, inner in self._schematics(comp) if idx else []:
                port                = next((c for c in self.kids(inner, 'Component') if self.prop(c, 'Type') == 'Output'
                                            and self.param(c, 'Index') == idx), None)
                res                 = self._trace_input(ctx + [(inner, comp)], self.prop(port, 'Name'), 1, depth) if port else None
                if res:
                    return res
            return [(name, '', '', '')]
        if typ == 'From':
            tag                     = self.param(comp, 'Tag')
            gotos                   = [(c_ctx, c) for c_ctx, c in self._walk(sch, ctx)
                                       if self.prop(c, 'Type') == 'Goto' and self.param(c, 'Tag') == tag] or \
                                      [(c_ctx, c) for c_ctx, c in self._walk(self._top(), [(self._top(), None)])
                                       if self.prop(c, 'Type') == 'Goto' and self.param(c, 'Tag') == tag]
            for g_ctx, g in gotos:
                res                 = self._trace_input(g_ctx, self.prop(g, 'Name'), 1, depth)
                if res:
                    return res
            return None
        if typ in self.PASS_THROUGH:
            return self._trace_input(ctx, name, 1, depth)
        if self._inputs(sch, name) == {'1'}:                                    # one input (RMS, gain, filter...): element-wise, prefixed
            res                     = self._trace_input(ctx, name, 1, depth)
            if res:
                return [(f"{name} {c}", s, l, h) for c, s, l, h in res]
        return [(name, '', '', '')]                                             # any other block: its own name, width 1

    def _inputs(self, schematic, name):
        """Input terminals of component name that a signal connection drives."""
        def dst(node):
            own                     = [self.prop(node, 'DstTerminal')] if self.prop(node, 'DstComponent') == name else []
            return own + [t for b in self.kids(node, 'Branch') for t in dst(b)]
        return {t for c in self.kids(schematic, 'Connection') if self.prop(c, 'Type') == 'Signal' for t in dst(c)}

    def _terminal_number(self, owner, kind, index):
        """Terminal number of port `index` of type kind on the subsystem owner (terminals count in their listed order)."""
        terms                       = self.kids(self._block(owner) or owner, 'Terminal') or self.kids(owner, 'Terminal')
        return next((k + 1 for k, t in enumerate(terms) if self.prop(t, 'Type') == kind and self.prop(t, 'Index') == index), None)

    def traced(self, n_columns=None, tofile=None):
        """Entries of the input of the To File block (named tofile, or the one whose width is n_columns)."""
        best                        = None
        for ctx, c in self._walk(self._top(), [(self._top(), None)]):
            if self.prop(c, 'Type') != 'ToFile' or (tofile and self.prop(c, 'Name') != tofile):
                continue
            res                     = self._trace_input(ctx, self.prop(c, 'Name'), 1, 0)
            if res and (n_columns is None or len(res) == n_columns):
                return res
            best                    = best or res
        return best

    #?------------------------------------------------------------------------------------------------------------------------------------
    #? Column names
    #?------------------------------------------------------------------------------------------------------------------------------------
    @staticmethod
    def header(csv_file):
        """Signal names of the To File header, without the time column."""
        with open(csv_file, encoding='utf-8', errors='ignore') as f:
            return [h.strip().strip('"') for h in f.readline().split(',')][1:]

    @staticmethod
    def _name(comp, probe, label):
        title                       = probe if probe and probe.lower().startswith(comp.lower()) else f"{comp} {probe}".strip()
        return f"{title} {label}".strip()                                       # 'Load:Load Voltage' -> 'Load Voltage'

    def columns(self, csv_file, tofile=None):
        """(names, unit hints) of the columns of csv_file."""
        header                      = self.header(csv_file)
        split                       = lambda h: (h.rpartition(':')[0], h.rpartition(':')[2]) if h.rpartition(':')[2].isdigit() else (h, '')
        groups                      = {}
        for h in header:
            groups[split(h)[0]]     = groups.get(split(h)[0], 0) + 1
        traced                      = None
        unnamed                     = lambda h: self.GENERIC.match(h) or not split(h)[0].partition(':')[2]   # 'ToFile_In_1', 'RMS Value:3'
        if any(unnamed(h) for h in header):
            traced                  = self.traced(len(header), tofile)
            traced                  = traced if traced and len(traced) == len(header) else None
        cache, names, hints         = {}, [], []
        for i, h in enumerate(header):
            key, idx                = split(h)
            comp, _, probe          = key.partition(':')
            if traced and unnamed(h):                                           # PLECS could not name it: traced name
                c, s, label, hint   = traced[i]
                names.append(self._name(c, s, label)); hints.append(f"{s} {hint}".lower())
                continue
            if key not in cache:
                entries             = [(l, '') for l in self.labels[key]] if key in self.labels else \
                                      self._mask_entries(self.find(self._top(), comp), probe)
                cache[key]          = entries if entries and (not idx or len(entries) == groups[key]) else None
            entries                 = cache[key]
            if idx and not entries and traced:                                  # vector the mask probe does not name
                c, s, label, hint   = traced[i]
                entries_i           = (label or idx, hint)
            else:
                entries_i           = entries[int(idx) - 1] if idx and entries else (idx, entries[0][1] if entries else '')
            names.append(self._name(comp, probe, entries_i[0]))
            hints.append(f"{probe} {entries_i[1]}".lower())
        return names, hints
#?----------------------------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        sys.exit('usage: python signals.py <result.csv> <model.plecs> [lib_dir]')
    for n, u in zip(*SignalNames.read(sys.argv[1], sys.argv[2], *(sys.argv[3:4]), units=True)):
        print(f"{u:8s} {n}")
